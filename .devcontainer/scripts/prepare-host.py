#!/usr/bin/env python3
"""Generate one ignored Compose override for the selected host and profile.

JSON is also valid YAML. Never invoke sudo, change drivers, or grant X11 access.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket

PROFILES = ('cpu', 'nvidia', 'nvidia-compat', 'amd', 'amd-wsl')
ROOT = Path(__file__).resolve().parents[2]
CDI_DIRECTORIES = (Path('/etc/cdi'), Path('/var/run/cdi'))
# Flight visualizer frontend (Vite) and backend, published on host loopback.
PUBLISHED_PORTS = (5173, 8000)
CONTAINER_HOME = PurePosixPath('/home/uas')
# on-create.sh runs the configured script from this read-only mount.
ON_CREATE_SCRIPT_TARGET = '/opt/no_crash/on-create-script'


def nvidia_cdi_available():
    # NixOS generates nvidia-container-toolkit.json; filenames aren't fixed by
    # CDI. Detect the NVIDIA kind in JSON or YAML specs in the standard paths.
    for directory in CDI_DIRECTORIES:
        for path in sorted(directory.glob('*.json')) + sorted(directory.glob('*.yaml')):
            try:
                content = path.read_text()
                if path.suffix == '.json':
                    spec = json.loads(content)
                    if isinstance(spec, dict) and spec.get('kind') == 'nvidia.com/gpu':
                        return True
                elif re.search(r'''(?m)^kind:\s*['"]?nvidia\.com/gpu['"]?\s*(?:#.*)?$''', content):
                    return True
            except (OSError, ValueError):
                continue
    return False


def personal_config_dir():
    """Host directory for personal setup: runtime-options.json and scripts."""
    config_home = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return config_home / 'no_crash'


def personal_state_dir():
    """Host directory backing the read/write state_mounts."""
    state_home = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
    return state_home / 'no_crash'


def read_personal_json(name):
    """Load an optional JSON object from the personal configuration directory."""
    retired = ROOT / '.devcontainer' / name
    path = personal_config_dir() / name
    if retired.exists():
        raise ValueError(f'.devcontainer/{name} is no longer read; move it to {path}')
    content = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(content, dict):
        raise ValueError(f'{name} must contain an object')
    return content


def read_runtime_options():
    options = read_personal_json('runtime-options.json')
    config = personal_config_dir()
    for retired in (ROOT / '.devcontainer/images.json', config / 'images.json'):
        if retired.exists():
            raise ValueError(f'{retired} is no longer read; move its entries to "images" in runtime-options.json')
    if (config / 'custom-install.sh').exists() and 'on_create_script' not in options:
        raise ValueError(f'{config / "custom-install.sh"} no longer runs automatically; '
                         'set "on_create_script": "custom-install.sh" in runtime-options.json')
    return options


def host_path(value, field):
    """Expand ~ and resolve relative paths against the personal configuration directory."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a nonempty path')
    return (personal_config_dir() / Path(value).expanduser()).resolve()


def container_path(value, field):
    """Absolute container path; ~ refers to /home/uas."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a nonempty path')
    path = PurePosixPath(value)
    if path.parts[:1] == ('~',):
        path = CONTAINER_HOME.joinpath(*path.parts[1:])
    if not path.is_absolute() or '..' in path.parts or path == PurePosixPath('/'):
        raise ValueError(f'{field} must be an absolute container path below /')
    return str(path)


def personal_volumes(options):
    """Bind mounts for on_create_script, extra_mounts, and state_mounts."""
    volumes, environment = [], {}
    script = options.get('on_create_script')
    if script is not None:
        source = host_path(script, 'on_create_script')
        if not source.is_file():
            raise ValueError(f'on_create_script is not a file: {source}')
        volumes.append(bind(source, ON_CREATE_SCRIPT_TARGET))
        environment['NO_CRASH_ON_CREATE_SCRIPT'] = ON_CREATE_SCRIPT_TARGET

    extra = options.get('extra_mounts', {})
    if not isinstance(extra, dict):
        raise ValueError('extra_mounts must map container paths to {"source": ..., "read_only": ...}')
    for target, mount in extra.items():
        field = f'extra_mounts[{target!r}]'
        if not isinstance(mount, dict) or set(mount) - {'source', 'read_only'}:
            raise ValueError(f'{field} must be an object with "source" and optional "read_only"')
        source = host_path(mount.get('source'), f'{field}.source')
        if not source.exists():
            raise ValueError(f'{field}.source is missing: {source}')
        read_only = mount.get('read_only', True)
        if not isinstance(read_only, bool):
            raise ValueError(f'{field}.read_only must be true or false')
        volumes.append(bind(source, container_path(target, field), read_only))

    state = options.get('state_mounts', {})
    if not isinstance(state, dict):
        raise ValueError('state_mounts must map container paths to state directory names')
    for target, name in state.items():
        field = f'state_mounts[{target!r}]'
        relative = PurePosixPath(name) if isinstance(name, str) else None
        if relative is None or not name.strip() or relative.is_absolute() or '..' in relative.parts:
            raise ValueError(f'{field} must be a relative directory name within {personal_state_dir()}')
        # main() creates these directories unless this is a dry run.
        source = personal_state_dir().absolute() / relative
        volumes.append(bind(source, container_path(target, field), False))
    return volumes, environment


def has_ipv6_loopback():
    # Rows are: address, interface index, prefix, scope, flags, interface name.
    try:
        rows = Path('/proc/net/if_inet6').read_text().splitlines()
    except OSError:
        return False
    return any(row.split()[:1] == ['0' * 31 + '1'] for row in rows)


def bind(source, target, read_only=True):
    return {
        'type': 'bind', 'source': str(source), 'target': target,
        'read_only': read_only, 'bind': {'create_host_path': False},
    }


def is_wsl():
    release = Path('/proc/sys/kernel/osrelease')
    return release.exists() and 'microsoft' in release.read_text().lower()


def make_override(profile, prebuilt, options, headless=False):
    host_wsl = is_wsl()
    if profile == 'amd-wsl' and not host_wsl:
        raise ValueError('amd-wsl requires a WSL2 Docker host; use amd on native Linux')
    if profile == 'amd' and host_wsl:
        raise ValueError('Use amd-wsl for AMD GPU compute on WSL2')

    service = {'environment': {}, 'volumes': [], 'devices': []}
    personal_config = personal_config_dir()
    if personal_config.is_dir():
        service['volumes'].append(bind(personal_config.resolve(), '/home/uas/.config/no_crash'))
    if prebuilt:
        images = options.get('images', {})
        if not isinstance(images, dict):
            raise ValueError('images must map profiles to image references')
        image = images.get(profile)
        if image is None:
            prefix = os.environ.get('NO_CRASH_IMAGE_PREFIX', 'ghcr.io/utat-uas/no_crash')
            tag = os.environ.get('NO_CRASH_IMAGE_TAG', '2026-10-28')
            image = f'{prefix}:{tag}-{profile}'
        if not isinstance(image, str) or not image.strip():
            raise ValueError('images references must be nonempty strings')
        service['image'] = image
        service['pull_policy'] = 'missing'

    if not headless and os.environ.get('DISPLAY'):
        service['environment'].update({'DISPLAY': os.environ['DISPLAY'], 'QT_X11_NO_MITSHM': '1'})
        x11_socket = Path('/tmp/.X11-unix')
        if x11_socket.exists():
            service['volumes'].append(bind(x11_socket.resolve(), '/tmp/.X11-unix', False))
        if host_wsl and Path('/mnt/wslg').exists():
            service['volumes'].append(bind('/mnt/wslg', '/mnt/wslg', False))
            for variable in ('WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR', 'PULSE_SERVER'):
                if os.environ.get(variable):
                    service['environment'][variable] = os.environ[variable]
        else:
            authority = Path(os.environ.get('XAUTHORITY', str(Path.home() / '.Xauthority')))
            if authority.is_file():
                service['volumes'].append(bind(authority.resolve(), '/home/uas/.Xauthority'))
                service['environment']['XAUTHORITY'] = '/home/uas/.Xauthority'
                # Xauthority FamilyLocal cookies can be keyed by host name.
                service['hostname'] = socket.gethostname()

    if host_wsl and Path('/dev/dxg').exists():
        service['devices'].append('/dev/dxg:/dev/dxg')
        if Path('/usr/lib/wsl/lib').exists():
            service['volumes'].append(bind('/usr/lib/wsl/lib', '/usr/lib/wsl/lib'))
            service['environment']['LD_LIBRARY_PATH'] = '/usr/lib/wsl/lib:/opt/ros/jazzy/lib'
    elif not host_wsl and not headless and Path('/dev/dri').exists():
        service['devices'].append('/dev/dri:/dev/dri')

    if profile.startswith('nvidia'):
        mode = options.get('nvidia_mode', 'auto')
        if mode not in ('auto', 'cdi', 'runtime'):
            raise ValueError('nvidia_mode must be auto, cdi, or runtime')
        use_cdi = mode == 'cdi' or (mode == 'auto' and nvidia_cdi_available())
        if use_cdi:
            service['devices'].append('nvidia.com/gpu=all')
        else:
            service['deploy'] = {'resources': {'reservations': {'devices': [
                {'driver': 'nvidia', 'count': 'all', 'capabilities': ['gpu']}
            ]}}}
        service['environment']['NVIDIA_DRIVER_CAPABILITIES'] = 'compute,utility,graphics,display,video'

    if profile == 'amd':
        if not Path('/dev/kfd').exists() or not Path('/dev/dri').exists():
            raise ValueError('AMD compute requires /dev/kfd and /dev/dri on the Linux host')
        service['devices'] = list(dict.fromkeys(service['devices'] + ['/dev/kfd:/dev/kfd', '/dev/dri:/dev/dri']))
        service['shm_size'] = '8gb'
    elif profile == 'amd-wsl':
        if not Path('/dev/dxg').exists() or not Path('/usr/lib/wsl/lib/libdxcore.so').is_file():
            raise ValueError('AMD WSL requires /dev/dxg and /usr/lib/wsl/lib/libdxcore.so')
        service['volumes'].append(bind('/usr/lib/wsl/lib/libdxcore.so', '/usr/lib/libdxcore.so'))
        # The image includes its own ROCDXG library and dids.conf.
        service['shm_size'] = '8gb'

    hardware = options.get('hardware_devices', [])
    if not isinstance(hardware, list) or not all(isinstance(p, str) and p.startswith('/dev/') for p in hardware):
        raise ValueError('hardware_devices must be a list of absolute /dev paths')
    for device in hardware:
        if not Path(device).exists():
            raise ValueError(f'Hardware device is missing: {device}')
        service['devices'].append(f'{device}:{device}')
    if not host_wsl:
        # Derive groups from the devices actually passed to Docker, including
        # every graphics card/render node on hosts with multiple GPUs.
        group_ids = set()
        for mapping in service['devices']:
            if not mapping.startswith('/dev/'):
                continue  # CDI manages its own device access.
            device = Path(mapping.split(':', 1)[0])
            if device.is_dir():
                group_ids.update(str(p.stat().st_gid) for p in device.rglob('*') if p.is_char_device())
            else:
                group_ids.add(str(device.stat().st_gid))
        if group_ids:
            service['group_add'] = sorted(group_ids)
    host_network = options.get('host_network', False)
    if not isinstance(host_network, bool):
        raise ValueError('host_network must be true or false')
    if host_network:
        if host_wsl:
            raise ValueError('The host_network override is supported only on native Linux')
        service['network_mode'] = 'host'
    else:
        # Loopback only, so nothing is exposed to the network. Browsers resolve
        # localhost to ::1 first, and Firefox WebSockets do not fall back to
        # IPv4, so publish on IPv6 loopback too where the host has it.
        host_ips = ['127.0.0.1'] + (['::1'] if not host_wsl and has_ipv6_loopback() else [])
        service['ports'] = [
            {'target': port, 'published': str(port), 'host_ip': ip, 'protocol': 'tcp'}
            for port in PUBLISHED_PORTS for ip in host_ips
        ]

    volumes, environment = personal_volumes(options)
    service['environment'].update(environment)
    targets = ['/home/uas/workspace'] + [v['target'] for v in service['volumes']]
    for volume in volumes:
        if volume['target'] in targets:
            raise ValueError(f'Mount target is already used: {volume["target"]}')
        targets.append(volume['target'])
        service['volumes'].append(volume)
    # Share one Compose project per profile across checkouts and image sources.
    return {
        'name': f'no_crash_{profile}',
        'services': {'uas': {k: v for k, v in service.items() if v != [] and v != {}}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, required=True)
    parser.add_argument('--prebuilt', action='store_true')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        options = read_runtime_options()
        override = make_override(args.profile, args.prebuilt, options, args.headless)
        content = json.dumps(override, indent=2) + '\n'
    except (OSError, ValueError) as error:
        parser.exit(2, f'Host configuration: {error}\n')
    if args.dry_run:
        print(content, end='')
        return
    state = personal_state_dir().absolute()
    for volume in override['services']['uas'].get('volumes', []):
        if Path(volume['source']).is_relative_to(state):
            Path(volume['source']).mkdir(parents=True, exist_ok=True)
    suffix = '-prebuilt' if args.prebuilt else ''
    destination = ROOT / '.devcontainer/runtime' / f'{args.profile}{suffix}.yaml'
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(content)
    temporary.replace(destination)


if __name__ == '__main__':
    main()
