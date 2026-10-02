#!/usr/bin/env python3
"""Regenerate the committed profile configurations; no JSON inheritance needed."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ('cpu', 'nvidia', 'nvidia-compat', 'amd', 'amd-wsl')
EXTENSIONS = [
    'ms-vscode.cpptools', 'ms-vscode.cmake-tools', 'ms-python.python',
    'ms-python.vscode-pylance', 'charliermarsh.ruff',
    'streetsidesoftware.code-spell-checker', 'eamodio.gitlens', 'svelte.svelte-vscode',
]


def expected_files():
    for profile in PROFILES:
        for prebuilt in (False, True):
            suffix = '-prebuilt' if prebuilt else ''
            directory = f'.devcontainer/{profile}{suffix}'
            config = {
                'name': f'no_crash Jazzy: {profile} ({"prebuilt" if prebuilt else "local image"})',
                'dockerComposeFile': ['../compose.yaml', 'compose.yaml', f'../runtime/{profile}{suffix}.yaml'],
                'service': 'uas', 'containerUser': 'uas', 'remoteUser': 'uas',
                'updateRemoteUserUID': True, 'workspaceFolder': '/home/uas/workspace',
                'shutdownAction': 'stopCompose', 'overrideCommand': False,
                'initializeCommand': ['python3', '${localWorkspaceFolder}/.devcontainer/scripts/prepare-host.py', '--profile', profile] + (['--prebuilt'] if prebuilt else []),
                'onCreateCommand': ['bash', '/home/uas/workspace/.devcontainer/on-create.sh'],
                'customizations': {'vscode': {'extensions': EXTENSIONS}},
            }
            service = {'image': f'no_crash:local-{profile}', 'pull_policy': 'never'}
            if prebuilt:
                service = {
                    'image': f'ghcr.io/utat-uas/no_crash:2026-10-01-{profile}',
                    'pull_policy': 'missing',
                }
            yield f'{directory}/devcontainer.json', json.dumps(config, indent=2) + '\n'
            # JSON is a YAML subset; retaining the .yaml suffix lets Compose
            # treat all shared and generated overrides uniformly.
            yield f'{directory}/compose.yaml', json.dumps({'services': {'uas': service}}, indent=2) + '\n'


def main():
    for filename, content in expected_files():
        path = ROOT / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


if __name__ == '__main__':
    main()
