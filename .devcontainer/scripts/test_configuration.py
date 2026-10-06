#!/usr/bin/env python3
"""Host configuration and lifecycle tests; never invoke Docker or install tools."""
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('prepare_host', ROOT / '.devcontainer/scripts/prepare-host.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)
spec = importlib.util.spec_from_file_location('package_opencv', ROOT / '.devcontainer/image/package-opencv.py')
opencv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(opencv)
spec = importlib.util.spec_from_file_location('validate', ROOT / '.devcontainer/scripts/validate.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


@contextmanager
def fake_host(wsl=False, files=(), environment=None):
    """Model real host device layouts without depending on this machine's GPU."""
    paths = set(files)
    with tempfile.TemporaryDirectory(prefix='no-crash-host-') as directory:
        root = Path(directory)
        (root / '.devcontainer').mkdir()
        cdi = root / 'cdi'
        cdi.mkdir()
        for path in paths:
            if path.startswith(('/etc/cdi/', '/var/run/cdi/')):
                content = '{"kind":"nvidia.com/gpu"}' if path.endswith('.json') else 'kind: nvidia.com/gpu\n'
                (cdi / Path(path).name).write_text(content)
        exists, is_file, stat = Path.exists, Path.is_file, Path.stat

        def fake_exists(p):
            return exists(p) if p.is_relative_to(root) else str(p) in paths

        def fake_is_file(p):
            return is_file(p) if p.is_relative_to(root) else str(p) in paths

        def fake_stat(p, *args, **kwargs):
            if p.is_relative_to(root):
                return stat(p, *args, **kwargs)
            return SimpleNamespace(st_gid=44, st_mode=0o20660)

        with patch.object(host, 'ROOT', root), patch.object(host, 'is_wsl', return_value=wsl), \
                patch.object(host, 'CDI_DIRECTORIES', (cdi,)), \
                patch.object(Path, 'exists', fake_exists), patch.object(Path, 'is_file', fake_is_file), \
                patch.object(Path, 'stat', fake_stat), \
                patch.dict(os.environ, environment or {}, clear=True):
            yield root


class HostConfigurationTests(unittest.TestCase):
    def test_personal_config_uses_host_xdg_directory_for_all_profiles(self):
        for profile in host.PROFILES:
            with fake_host(wsl=profile == 'amd-wsl', files=[
                '/dev/kfd', '/dev/dri', '/dev/dxg', '/usr/lib/wsl/lib',
                '/usr/lib/wsl/lib/libdxcore.so',
            ]) as root:
                config_home = root / 'custom config'
                personal_config = config_home / 'no_crash'
                personal_config.mkdir(parents=True)
                with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(config_home)}):
                    for prebuilt in (False, True):
                        with self.subTest(profile=profile, prebuilt=prebuilt):
                            service = host.make_override(profile, prebuilt, {})['services']['uas']
                            self.assertIn(host.bind(personal_config, '/home/uas/.config/no_crash'),
                                          service['volumes'])

    def test_personal_config_defaults_to_home_for_unset_or_empty_xdg(self):
        with fake_host() as root:
            personal_config = root / '.config/no_crash'
            personal_config.mkdir(parents=True)
            for environment in ({'HOME': str(root)}, {'HOME': str(root), 'XDG_CONFIG_HOME': ''}):
                with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
                    service = host.make_override('cpu', False, {})['services']['uas']
                    self.assertEqual(service['volumes'], [
                        host.bind(personal_config, '/home/uas/.config/no_crash'),
                    ])

    def test_missing_personal_config_is_skipped_without_creating_it(self):
        with fake_host() as root, patch.dict(os.environ, {'XDG_CONFIG_HOME': str(root)}):
            service = host.make_override('cpu', False, {})['services']['uas']
            self.assertNotIn('volumes', service)
            self.assertFalse((root / 'no_crash').exists())

    def test_compose_projects_depend_only_on_profile(self):
        with fake_host():
            cpu = host.make_override('cpu', False, {})['name']
            self.assertEqual(host.make_override('cpu', False, {})['name'], cpu)
            nvidia = host.make_override('nvidia', False, {})['name']
            prebuilt = host.make_override('cpu', True, {})['name']
            with patch.object(host, 'ROOT', host.ROOT.parent / 'another' / host.ROOT.name):
                other_checkout = host.make_override('cpu', False, {})['name']
            self.assertEqual(cpu, 'no_crash_cpu')
            self.assertEqual(nvidia, 'no_crash_nvidia')
            self.assertEqual(prebuilt, cpu)
            self.assertEqual(other_checkout, cpu)

    def test_headless_cpu_needs_no_gpu_or_display(self):
        with fake_host(files=['/dev/dri']):
            service = host.make_override('cpu', False, {}, headless=True)['services']['uas']
            self.assertNotIn('devices', service)
            self.assertNotIn('privileged', service)

    def test_native_display_socket_and_authority_are_mapped(self):
        with fake_host(files=['/tmp/.X11-unix', '/tmp/no-crash-authority'], environment={
            'DISPLAY': ':1', 'XAUTHORITY': '/tmp/no-crash-authority',
        }):
            service = host.make_override('cpu', False, {})['services']['uas']
            self.assertEqual(service['environment']['DISPLAY'], ':1')
            authority = next(v for v in service['volumes'] if v['target'] == '/home/uas/.Xauthority')
            self.assertTrue(authority['read_only'])
            self.assertFalse(authority['bind']['create_host_path'])

    def test_nvidia_uses_runtime_when_no_cdi_spec_exists(self):
        with fake_host():
            service = host.make_override('nvidia', False, {})['services']['uas']
            devices = service['deploy']['resources']['reservations']['devices']
            self.assertEqual(devices[0]['driver'], 'nvidia')
            self.assertNotIn('privileged', service)

    def test_nvidia_automatically_uses_host_cdi(self):
        with fake_host(files=['/etc/cdi/nvidia.yaml']):
            service = host.make_override('nvidia-compat', False, {})['services']['uas']
            self.assertIn('nvidia.com/gpu=all', service['devices'])
            self.assertNotIn('deploy', service)

    def test_nvidia_mode_can_be_overridden(self):
        with fake_host(files=['/etc/cdi/nvidia.yaml']):
            service = host.make_override('nvidia', False, {'nvidia_mode': 'runtime'})['services']['uas']
            self.assertIn('deploy', service)
            with self.assertRaises(ValueError):
                host.make_override('nvidia', False, {'nvidia_mode': 'invalid'})

    def test_nixos_json_cdi_spec_is_detected(self):
        with fake_host(files=['/var/run/cdi/nvidia-container-toolkit.json']):
            service = host.make_override('nvidia', False, {})['services']['uas']
            self.assertIn('nvidia.com/gpu=all', service['devices'])
            self.assertNotIn('deploy', service)

    def test_unrelated_cdi_spec_does_not_select_nvidia_cdi(self):
        with fake_host() as root:
            (root / 'cdi/other.json').write_text('{"kind":"other.com/device"}')
            service = host.make_override('nvidia', False, {})['services']['uas']
            self.assertIn('deploy', service)

    def test_native_amd_passes_devices_and_host_groups(self):
        with fake_host(files=['/dev/kfd', '/dev/dri', '/dev/dri/renderD128']):
            service = host.make_override('amd', False, {})['services']['uas']
            self.assertIn('/dev/kfd:/dev/kfd', service['devices'])
            self.assertIn('/dev/dri:/dev/dri', service['devices'])
            self.assertEqual(service['group_add'], ['44'])

    def test_native_amd_requires_devices(self):
        with fake_host():
            with self.assertRaisesRegex(ValueError, '/dev/kfd'):
                host.make_override('amd', False, {})

    def test_all_mapped_graphics_nodes_contribute_groups(self):
        nodes = [Path('/dev/dri/card1'), Path('/dev/dri/renderD129')]
        with fake_host(files=['/dev/dri'], environment={'DISPLAY': ':0'}), \
                patch.object(Path, 'is_dir', return_value=True), \
                patch.object(Path, 'rglob', return_value=iter(nodes)), \
                patch.object(Path, 'is_char_device', return_value=True), \
                patch.object(Path, 'stat', side_effect=[SimpleNamespace(st_gid=44),
                                                       SimpleNamespace(st_gid=303)]):
            service = host.make_override('cpu', False, {})['services']['uas']
            self.assertEqual(service['group_add'], ['303', '44'])

    def test_amd_wsl_uses_dxcore_without_kfd(self):
        with fake_host(wsl=True, files=['/dev/dxg', '/usr/lib/wsl/lib', '/usr/lib/wsl/lib/libdxcore.so']):
            service = host.make_override('amd-wsl', False, {})['services']['uas']
            self.assertEqual(service['devices'], ['/dev/dxg:/dev/dxg'])
            self.assertTrue(any(v['target'] == '/usr/lib/libdxcore.so' for v in service['volumes']))
            self.assertNotIn('privileged', service)

    def test_amd_wsl_requires_wsl_and_dxcore(self):
        with fake_host():
            with self.assertRaisesRegex(ValueError, 'WSL2'):
                host.make_override('amd-wsl', False, {})
        with fake_host(wsl=True):
            with self.assertRaisesRegex(ValueError, 'libdxcore'):
                host.make_override('amd-wsl', False, {})
            with self.assertRaisesRegex(ValueError, 'amd-wsl'):
                host.make_override('amd', False, {})

    def test_wslg_includes_display_and_audio(self):
        with fake_host(wsl=True, files=['/mnt/wslg', '/dev/dxg', '/usr/lib/wsl/lib'], environment={
            'DISPLAY': ':0', 'WAYLAND_DISPLAY': 'wayland-0', 'XDG_RUNTIME_DIR': '/mnt/wslg/runtime-dir',
            'PULSE_SERVER': 'unix:/mnt/wslg/PulseServer',
        }):
            service = host.make_override('cpu', False, {})['services']['uas']
            self.assertEqual(service['environment']['PULSE_SERVER'], 'unix:/mnt/wslg/PulseServer')
            self.assertIn('/dev/dxg:/dev/dxg', service['devices'])

    def test_prebuilt_references_can_be_digest_pinned(self):
        with fake_host() as root:
            image = 'ghcr.io/example/no_crash@sha256:' + 'a' * 64
            (root / '.devcontainer/images.json').write_text(json.dumps({'cpu': image}))
            service = host.make_override('cpu', True, {})['services']['uas']
            self.assertEqual(service['image'], image)
            self.assertNotIn('build', service)

    def test_hardware_and_host_network_are_explicit(self):
        with fake_host(files=['/dev/ttyACM0']):
            service = host.make_override('cpu', False, {
                'hardware_devices': ['/dev/ttyACM0'], 'host_network': True,
            })['services']['uas']
            self.assertEqual(service['network_mode'], 'host')
            self.assertEqual(service['devices'], ['/dev/ttyACM0:/dev/ttyACM0'])
            with self.assertRaises(ValueError):
                host.make_override('cpu', False, {'hardware_devices': ['/tmp/not-a-device']})
        with fake_host(wsl=True):
            with self.assertRaises(ValueError):
                host.make_override('cpu', False, {'host_network': True})


class LauncherTests(unittest.TestCase):
    def launch(self, *arguments, missing_tools=()):
        with tempfile.TemporaryDirectory(prefix='no-crash-launcher-') as directory:
            root = Path(directory)
            shutil.copy2(ROOT / 'enter.sh', root / 'enter.sh')
            tools = root / 'tools'
            tools.mkdir()
            commands = root / 'commands.jsonl'
            fake = '''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

name = Path(sys.argv[0]).name
arguments = sys.argv[1:]
with open(os.environ['NO_CRASH_TEST_COMMANDS'], 'a') as stream:
    stream.write(json.dumps([name, *arguments]) + '\\n')
'''
            for name in ('docker', 'devcontainer'):
                if name in missing_tools:
                    continue
                path = tools / name
                path.write_text(fake)
                path.chmod(0o755)
            # Isolate PATH so a missing fake tool cannot resolve to a host tool.
            for name in ('bash', 'dirname', 'python3'):
                (tools / name).symlink_to(shutil.which(name))
            environment = dict(os.environ, PATH=str(tools),
                               NO_CRASH_TEST_COMMANDS=str(commands))
            result = subprocess.run(['bash', str(root / 'enter.sh'), *arguments],
                                    env=environment, capture_output=True, text=True)
            events = [json.loads(line) for line in commands.read_text().splitlines()] if commands.exists() else []
            return result, events

    def test_prebuilt_is_default_for_cpu_and_selected_profile(self):
        for arguments, profile in [(('--profile', 'cpu'), 'cpu'), (('--profile', 'nvidia'), 'nvidia')]:
            with self.subTest(profile=profile):
                result, events = self.launch(*arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([event[:2] for event in events],
                                 [['devcontainer', 'up'], ['devcontainer', 'exec']])
                for event in events:
                    self.assertEqual(event[event.index('--config') + 1],
                                     f'.devcontainer/{profile}-prebuilt/devcontainer.json')
                self.assertNotIn('--remove-existing-container', events[0])

    def test_local_selection_delegates_build_to_devcontainers(self):
        result, events = self.launch('--profile', 'nvidia', '--local')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([event[:2] for event in events],
                         [['devcontainer', 'up'], ['devcontainer', 'exec']])
        for event in events:
            self.assertEqual(event[event.index('--config') + 1], '.devcontainer/nvidia/devcontainer.json')
        self.assertNotIn('--remove-existing-container', events[0])

    def test_rebuild_recreates_prebuilt_and_local_containers(self):
        for mode, suffix in [((), '-prebuilt'), (('--local',), '')]:
            with self.subTest(mode=mode):
                result, events = self.launch('--profile', 'nvidia', '--rebuild', *mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([event[:2] for event in events],
                                 [['devcontainer', 'up'], ['devcontainer', 'exec']])
                self.assertIn('--remove-existing-container', events[0])
                self.assertNotIn('--remove-existing-container', events[1])
                for event in events:
                    self.assertEqual(event[event.index('--config') + 1],
                                     f'.devcontainer/nvidia{suffix}/devcontainer.json')

    def test_retired_flags_fail_before_startup(self):
        for flag in ('--build', '--prebuilt'):
            with self.subTest(flag=flag):
                result, events = self.launch(flag)
                self.assertEqual(result.returncode, 2)
                self.assertIn(f'Unknown argument: {flag}', result.stderr)
                self.assertEqual(events, [])

    def test_help_describes_image_selection_and_recreation(self):
        expected, _ = self.launch('--help')
        for arguments in [(), ('--help',), ('-h',)]:
            with self.subTest(arguments=arguments):
                result, events = self.launch(*arguments, missing_tools=('docker', 'devcontainer'))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected.stdout)
                self.assertIn('--local', result.stdout)
                self.assertIn('--rebuild', result.stdout)
                self.assertIn('No arguments prints this help', result.stdout)
                self.assertEqual(events, [])

    def test_missing_cli_fails_before_startup(self):
        result, events = self.launch('--profile', 'cpu', missing_tools=('devcontainer',))
        self.assertEqual(result.returncode, 1)
        self.assertIn('Missing host tool: devcontainer', result.stderr)
        self.assertEqual(events, [])


class ValidationScopeTests(unittest.TestCase):
    def test_project_environments_and_personal_installers_are_excluded(self):
        with tempfile.TemporaryDirectory(prefix='no-crash-validation-') as directory:
            root = Path(directory)
            paths = ['.devcontainer/scripts/check.py', '.devcontainer/image/setup.sh',
                     '.devcontainer/image/bin/tool', '.devcontainer/custom-install.sh',
                     'flight_visualizer/backend/.venv/dependency.py', 'hardware_manager/tool.sh',
                     'enter.sh']
            for name in paths:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            python, shell = validator.source_files(root)
            self.assertEqual(python, [root / '.devcontainer/scripts/check.py'])
            self.assertEqual(set(shell), {root / '.devcontainer/image/setup.sh',
                                          root / '.devcontainer/image/bin/tool', root / 'enter.sh'})


class ImageHelperTests(unittest.TestCase):
    def invoke(self, script, *arguments, environment=None):
        with tempfile.TemporaryDirectory(prefix='no-crash-image-helpers-') as directory:
            root = Path(directory)
            config = root / '.devcontainer'
            config.mkdir()
            for name in ('build-images.sh', 'push-images.sh', 'versions.env'):
                shutil.copy2(ROOT / '.devcontainer' / name, config / name)
            tools = root / 'tools'
            tools.mkdir()
            commands = root / 'commands.jsonl'
            fake = tools / 'docker'
            fake.write_text('''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

arguments = sys.argv[1:]
with open(os.environ['NO_CRASH_TEST_COMMANDS'], 'a') as stream:
    stream.write(json.dumps({'arguments': arguments, 'cwd': os.getcwd()}) + '\\n')
if arguments[:2] == ['image', 'inspect']:
    if arguments[2] == os.environ.get('NO_CRASH_TEST_MISSING_IMAGE'):
        sys.exit(1)
    print('sha256:' + arguments[2].removeprefix('no_crash:local-'))
if arguments[0] in ('push', 'buildx') and os.environ.get('NO_CRASH_TEST_FAIL_COMMAND') == arguments[0]:
    sys.exit(17)
''')
            fake.chmod(0o755)
            env = {key: value for key, value in os.environ.items()
                   if key not in ('NO_CRASH_IMAGE_PREFIX', 'NO_CRASH_IMAGE_TAG')}
            env.update(PATH=f'{tools}:{os.environ["PATH"]}',
                       NO_CRASH_TEST_COMMANDS=str(commands), NO_CRASH_BUILD_JOBS='4')
            env.update(environment or {})
            # Invoke from outside the checkout to verify the relocated helpers
            # still use the repository root as the Docker build context.
            result = subprocess.run(['bash', str(config / script), *arguments],
                                    cwd=tools, env=env, capture_output=True, text=True)
            events = [json.loads(line) for line in commands.read_text().splitlines()] if commands.exists() else []
            self.assertTrue(all(event['cwd'] == str(root) for event in events))
            return result, [event['arguments'] for event in events]

    def test_all_builds_use_local_tags_and_stop_on_failure(self):
        result, events = self.invoke('build-images.sh', 'all')
        self.assertEqual(result.returncode, 0, result.stderr)
        builds = [event for event in events if event[:2] == ['buildx', 'build']]
        profiles = ['cpu', 'nvidia', 'nvidia-compat', 'amd', 'amd-wsl']
        self.assertEqual([event[event.index('--target') + 1] for event in builds], profiles)
        self.assertEqual([event[event.index('--tag') + 1] for event in builds],
                         [f'no_crash:local-{profile}' for profile in profiles])
        result, events = self.invoke('build-images.sh', 'all',
                                    environment={'NO_CRASH_TEST_FAIL_COMMAND': 'buildx'})
        self.assertEqual(result.returncode, 17)
        self.assertEqual(len(events), 1)

    def test_all_images_are_inspected_before_publishing_exact_ids(self):
        result, events = self.invoke('push-images.sh', 'all')
        self.assertEqual(result.returncode, 0, result.stderr)
        profiles = ['cpu', 'nvidia', 'nvidia-compat', 'amd', 'amd-wsl']
        self.assertEqual([event[2] for event in events[:5]],
                         [f'no_crash:local-{profile}' for profile in profiles])
        snapshot = next(line.split("'", 2)[1] for line in
                        (ROOT / '.devcontainer/versions.env').read_text().splitlines()
                        if line.startswith('SNAPSHOT_DATE='))
        tags = [event for event in events if event[0] == 'tag']
        self.assertEqual(tags, [['tag', f'sha256:{profile}', f'ghcr.io/utat-uas/no_crash:{snapshot}-{profile}']
                                for profile in profiles])
        self.assertEqual([event[1] for event in events if event[0] == 'push'],
                         [event[2] for event in tags])

    def test_missing_last_image_prevents_all_publishing(self):
        result, events = self.invoke('push-images.sh', 'all',
                                    environment={'NO_CRASH_TEST_MISSING_IMAGE': 'no_crash:local-amd-wsl'})
        self.assertEqual(result.returncode, 1)
        self.assertIn('Missing local image', result.stderr)
        self.assertFalse(any(event[0] in ('tag', 'push') for event in events))

    def test_custom_destination_single_profile_and_push_failure(self):
        env = {'NO_CRASH_IMAGE_PREFIX': 'ghcr.io/example/custom', 'NO_CRASH_IMAGE_TAG': 'v2'}
        result, events = self.invoke('push-images.sh', 'nvidia-compat', environment=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events[-1], ['push', 'ghcr.io/example/custom:v2-nvidia-compat'])
        self.assertEqual(len(events), 3)
        result, events = self.invoke('push-images.sh', 'all',
                                    environment={'NO_CRASH_TEST_FAIL_COMMAND': 'push'})
        self.assertEqual(result.returncode, 17)
        self.assertEqual(sum(event[0] == 'push' for event in events), 1)

    def test_invalid_publish_settings_fail_before_docker_calls(self):
        cases = [({'NO_CRASH_IMAGE_PREFIX': 'docker.io/example/no_crash'}, 'all'),
                 ({'NO_CRASH_IMAGE_TAG': 'bad/tag'}, 'all'), ({}, 'typo')]
        for env, profile in cases:
            with self.subTest(environment=env, profile=profile):
                result, events = self.invoke('push-images.sh', profile, environment=env)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(events, [])


class StoragePermissionTests(unittest.TestCase):
    def test_shell_environment_resets_inherited_umask_for_new_files(self):
        with tempfile.TemporaryDirectory(prefix='no-crash-umask-') as directory:
            root = Path(directory)
            script = '''umask 0000
source "$1"
: > "$2/file"
mkdir "$2/directory"
umask
'''
            result = subprocess.run(
                ['bash', '-c', script, 'umask-test',
                 str(ROOT / '.devcontainer/image/environment.sh'), str(root)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), '0022')
            self.assertEqual((root / 'file').stat().st_mode & 0o777, 0o644)
            self.assertEqual((root / 'directory').stat().st_mode & 0o777, 0o755)

    def normalize(self, root):
        # Storage normalization needs no release pins or network access.
        pins = root / 'versions.env'
        pins.write_text('')
        script = (ROOT / '.devcontainer/image/helpers.sh').read_text().replace(
            'source /usr/local/share/no-crash/versions.env', 'source "$NO_CRASH_TEST_PINS"')
        result = subprocess.run(['bash', '-c', script + '\nmake_user_storage_writable "$1"\n',
                                 'storage-test', str(root)],
                                env={**os.environ, 'NO_CRASH_TEST_PINS': str(pins)},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_installed_artifacts_writable_without_making_data_executable(self):
        with tempfile.TemporaryDirectory(prefix='no-crash-storage-') as directory:
            root = Path(directory)
            package = root / '.venvs/vision'
            package.mkdir(parents=True)
            executable = package / 'tool'
            data = package / 'pyvenv.cfg'
            executable.write_text('executable fixture')
            data.write_text('configuration fixture')
            executable.chmod(0o700)
            data.chmod(0o600)
            package.chmod(0o700)
            self.normalize(root)
            self.assertEqual(executable.stat().st_mode & 0o777, 0o777)
            self.assertEqual(data.stat().st_mode & 0o777, 0o666)
            self.assertEqual(package.stat().st_mode & 0o777, 0o777)

    def test_cache_mounts_and_external_symlink_targets_are_untouched(self):
        with tempfile.TemporaryDirectory(prefix='no-crash-storage-') as directory:
            root = Path(directory) / 'storage'
            cache = root / '.cargo/registry'
            cache.mkdir(parents=True)
            cache_file = cache / 'cached-package'
            cache_file.write_text('cache fixture')
            cache_file.chmod(0o600)
            cache.chmod(0o700)
            outside = Path(directory) / 'outside'
            outside.write_text('external fixture')
            outside.chmod(0o400)
            (root / 'external-link').symlink_to(outside)
            self.normalize(root)
            self.assertEqual(cache.stat().st_mode & 0o777, 0o700)
            self.assertEqual(cache_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(outside.stat().st_mode & 0o777, 0o400)


class OpenCVPackagingTests(unittest.TestCase):
    def test_extension_can_be_found_after_moving_package_into_venv(self):
        with tempfile.TemporaryDirectory(prefix='no-crash-opencv-') as directory:
            root = Path(directory)
            stage = root / 'build/opencv-wheel'
            extension = stage / 'cv2/python-3.12/cv2.cpython-312-x86_64-linux-gnu.so'
            extension.parent.mkdir(parents=True)
            extension.write_bytes(b'fixture: native extension is not loaded by this test')
            config = stage / 'cv2/config-3.12.py'
            config.write_text(f'PYTHON_EXTENSIONS_PATHS = [{str(extension.parent)!r}] + PYTHON_EXTENSIONS_PATHS\n')
            opencv.relocate_extension_config(stage)
            installed = root / 'venv/lib/python3.12/site-packages/cv2'
            installed.parent.mkdir(parents=True)
            shutil.move(str(stage / 'cv2'), installed)
            shutil.rmtree(stage)
            namespace = {'os': os, 'LOADER_DIR': str(installed), 'PYTHON_EXTENSIONS_PATHS': []}
            exec((installed / config.name).read_text(), namespace)
            candidates = [Path(p) / extension.name for p in namespace['PYTHON_EXTENSIONS_PATHS']]
            self.assertTrue(any(p.is_file() for p in candidates), candidates)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='no-crash-lifecycle-')
        self.home = Path(self.directory.name)
        self.workspace = self.home / 'workspace'
        self.config = self.workspace / '.devcontainer'
        self.config.mkdir(parents=True)
        self.personal_config = self.home / '.config/no_crash'
        self.personal_config.mkdir(parents=True)
        shutil.copy(ROOT / '.devcontainer/on-create.sh', self.config / 'on-create.sh')
        (self.home / '.bashrc').write_text('# My settings\n')
        self.environment = {**os.environ, 'HOME': str(self.home), 'GIT_CONFIG_GLOBAL': str(self.home / '.gitconfig')}
        self.environment.pop('XDG_CONFIG_HOME', None)

    def tearDown(self):
        self.directory.cleanup()

    def run_hook(self):
        return subprocess.run(['bash', str(self.config / 'on-create.sh')], cwd=self.workspace,
                              env=self.environment, capture_output=True, text=True)

    def test_missing_custom_script_and_repeated_setup(self):
        for _ in range(2):
            result = self.run_hook()
            self.assertEqual(result.returncode, 0, result.stderr)
        rc = (self.home / '.bashrc').read_text()
        self.assertIn('# My settings', rc)
        self.assertEqual(rc.count('# BEGIN no_crash workspace'), 1)
        self.assertEqual((self.home / '.gitconfig').read_text().count('directory ='), 1)
        self.assertTrue((self.home / '.hushlogin').is_file())

    def test_custom_script_runs_through_bash_in_workspace(self):
        (self.personal_config / 'custom-install.sh').write_text('printf "%s\\n" "$PWD" > custom-result\n')
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.workspace / 'custom-result').read_text().strip(), str(self.workspace))

    def test_custom_script_failure_is_visible(self):
        (self.personal_config / 'custom-install.sh').write_text('exit 23\n')
        self.assertEqual(self.run_hook().returncode, 23)

    def test_custom_script_uses_explicit_xdg_config_home(self):
        config_home = self.home / 'custom config'
        (config_home / 'no_crash').mkdir(parents=True)
        (config_home / 'no_crash/custom-install.sh').write_text(': > custom-result\n')
        (self.personal_config / 'custom-install.sh').write_text('exit 23\n')
        self.environment['XDG_CONFIG_HOME'] = str(config_home)
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.workspace / 'custom-result').is_file())

    def test_empty_xdg_config_home_uses_default(self):
        self.environment['XDG_CONFIG_HOME'] = ''
        (self.personal_config / 'custom-install.sh').write_text(': > custom-result\n')
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.workspace / 'custom-result').is_file())

    def test_legacy_workspace_installer_is_skipped(self):
        (self.config / 'custom-install.sh').write_text('exit 23\n')
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_creation_and_future_shells_reset_inherited_umask(self):
        (self.personal_config / 'custom-install.sh').write_text(': > custom-result\n')
        result = subprocess.run(
            ['bash', '-c', 'umask 0000; exec bash "$1"', 'umask-test',
             str(self.config / 'on-create.sh')],
            cwd=self.workspace, env=self.environment, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / '.hushlogin').stat().st_mode & 0o777, 0o644)
        self.assertEqual((self.workspace / 'custom-result').stat().st_mode & 0o777, 0o644)
        result = subprocess.run(
            ['bash', '-c', 'umask 0000; source "$HOME/.bashrc"; umask'],
            env=self.environment, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '0022')


if __name__ == '__main__':
    unittest.main()
