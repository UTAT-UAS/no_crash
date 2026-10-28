from setuptools import setup

package_name = 'flight_visualizer_bridge'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
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
