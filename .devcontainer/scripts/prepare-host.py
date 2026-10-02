#!/usr/bin/env python3
"""Generate one ignored Compose override for the selected host and profile.

JSON is also valid YAML. Never invoke sudo, change drivers, or grant X11 access.
"""
import argparse
import json
import os
from pathlib import Path
import re
import socket

PROFILES = ('cpu', 'nvidia', 'nvidia-compat', 'amd', 'amd-wsl')
ROOT = Path(__file__).resolve().parents[2]
CDI_DIRECTORIES = (Path('/etc/cdi'), Path('/var/run/cdi'))


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
    if prebuilt:
        images_file = ROOT / '.devcontainer/images.json'
        images = json.loads(images_file.read_text()) if images_file.exists() else {}
        if not isinstance(images, dict):
            raise ValueError('images.json must contain an object')
        image = images.get(profile)
        if image is None:
            prefix = os.environ.get('NO_CRASH_IMAGE_PREFIX', 'ghcr.io/utat-uas/no_crash')
            tag = os.environ.get('NO_CRASH_IMAGE_TAG', '2026-10-01')
            image = f'{prefix}:{tag}-{profile}'
        if not isinstance(image, str) or not image.strip():
            raise ValueError('images.json references must be nonempty strings')
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
    options_path = ROOT / '.devcontainer/runtime-options.json'
    try:
        options = json.loads(options_path.read_text()) if options_path.exists() else {}
        if not isinstance(options, dict):
            raise ValueError('runtime-options.json must contain an object')
        content = json.dumps(make_override(args.profile, args.prebuilt, options, args.headless), indent=2) + '\n'
    except (OSError, ValueError) as error:
        parser.exit(2, f'Host configuration: {error}\n')
    if args.dry_run:
        print(content, end='')
        return
    suffix = '-prebuilt' if args.prebuilt else ''
    destination = ROOT / '.devcontainer/runtime' / f'{args.profile}{suffix}.yaml'
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(content)
    temporary.replace(destination)


if __name__ == '__main__':
    main()
