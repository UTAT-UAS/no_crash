"""Launch the flight_core central offboard node."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """Start flight_core_cpp with configurable mode and setpoint rate."""
    mode = LaunchConfiguration('mode')
    rate_hz = LaunchConfiguration('rate_hz')
    return LaunchDescription([
        DeclareLaunchArgument(
            'mode', default_value='real', choices=['sim', 'real'],
            description="'sim' allows arming requests; 'real' rejects them"),
        DeclareLaunchArgument(
            'rate_hz', default_value='20.0',
            description='Offboard heartbeat and goto setpoint rate'),
        Node(
            package='flight_core',
            executable='flight_core_cpp',
            output='screen',
            parameters=[{
                'mode': mode,
                'rate_hz': ParameterValue(rate_hz, value_type=float),
            }],
        ),
    ])
