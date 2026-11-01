from pathlib import Path
import subprocess

from setuptools import setup

package_name = 'flight_visualizer_bridge'
here = Path(__file__).resolve().parent

# Generate the protobuf module into the package (ignored by git), so that
# --symlink-install picks it up too.
subprocess.run(
    [
        'protoc',
        f'--proto_path={here / "proto"}',
        f'--python_out={here / package_name}',
        f'--pyi_out={here / package_name}',
        'flight_visualizer.proto',
    ],
    check=True,
)

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    package_data={package_name: ['*.pyi']},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/proto', ['proto/flight_visualizer.proto']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='UTAT UAS',
    maintainer_email='contact@utat.ca',
    description='Streams drone state to the flight visualizer over TCP and '
    'forwards its commands to flight_core.',
    license='GPL-3.0-only',
    entry_points={
        'console_scripts': [
            'flight_visualizer_bridge = flight_visualizer_bridge.bridge:main',
        ],
    },
)
