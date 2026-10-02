#!/usr/bin/env python3
"""Validate checked-in inputs and merged Compose models without building images."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    for path in ROOT.rglob('*.py'):
        if '.git' not in path.parts:
            ast.parse(path.read_text(), filename=str(path))
    for path in list(ROOT.rglob('*.sh')) + list((ROOT / '.devcontainer/image/bin').iterdir()):
        if path.name != 'custom-install.sh':
            run('bash', '-n', str(path))
    pins = {}
    for line in (ROOT / '.devcontainer/versions.env').read_text().splitlines():
        if line and not line.startswith('#'):
            key, value = line.split('=', 1)
            pins[key] = value.strip("'")
            if key.endswith('_REVISION'):
                assert re.fullmatch('[0-9a-f]{40}', pins[key]), key
            if key.endswith('_SHA256'):
                assert re.fullmatch('[0-9a-f]{64}', pins[key]), key
    dockerfile = (ROOT / '.devcontainer/Dockerfile').read_text()
    assert re.search(r'^FROM osrf/ros:jazzy-desktop-full@sha256:[0-9a-f]{64} AS system$', dockerfile, re.M)
    targets = set(re.findall(r'^FROM .+ AS ([\w-]+)$', dockerfile, re.M))
    for profile in ('cpu', 'nvidia', 'nvidia-compat', 'amd', 'amd-wsl'):
        assert profile in targets

    spec = importlib.util.spec_from_file_location('generate_configs', ROOT / '.devcontainer/scripts/generate-configs.py')
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    for filename, expected in generator.expected_files():
        assert (ROOT / filename).read_text() == expected, f'{filename}: regenerate profile configurations'

    # Empty host overrides validate portable profile structure. Machine-specific
    # override contents and failure paths are exercised by the host tests.
    with tempfile.TemporaryDirectory(prefix='no-crash-compose-') as directory:
        override = Path(directory) / 'runtime.yaml'
        override.write_text('{"services":{"uas":{}}}\n')
        for profile in generator.PROFILES:
            for suffix in ('', '-prebuilt'):
                config_path = ROOT / f'.devcontainer/{profile}{suffix}/devcontainer.json'
                config = json.loads(config_path.read_text())
                assert config['remoteUser'] == 'uas' and config['updateRemoteUserUID']
                files = [config_path.parent / f for f in config['dockerComposeFile'][:2]]
                command = ['docker', 'compose']
                for path in files + [override]:
                    command.extend(['-f', str(path)])
                result = subprocess.run(command + ['config', '--format', 'json'], cwd=ROOT,
                                        check=True, capture_output=True, text=True)
                service = json.loads(result.stdout)['services']['uas']
                assert not service.get('privileged') and service['user'] == 'uas'
                assert service['volumes'][0]['source'] == str(ROOT)
                assert 'build' not in service, 'Startup must reuse the selected image'
                if not suffix:
                    assert service['image'] == f'no_crash:local-{profile}'
                    assert service['pull_policy'] == 'never'
    shellcheck = shutil.which('shellcheck')
    if shellcheck:
        paths = list((ROOT / '.devcontainer/image').glob('*.sh')) + list((ROOT / '.devcontainer/image/bin').iterdir())
        paths += list((ROOT / '.devcontainer/scripts').glob('*.sh'))
        paths += list((ROOT / '.devcontainer').glob('*.sh'))
        paths += [ROOT / 'enter.sh']
        run(shellcheck, '--severity=warning', '--exclude=SC1091', *(str(p) for p in paths))
    hadolint = shutil.which('hadolint')
    if hadolint:
        run(hadolint, '.devcontainer/Dockerfile')
    run('python3', str(ROOT / '.devcontainer/scripts/test_configuration.py'))
    print('Static validation passed. No image builds or container starts were performed.')


if __name__ == '__main__':
    main()
