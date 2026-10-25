#include <memory>

#include "flight_core/flight_core_node.hpp"
#include "rclcpp/rclcpp.hpp"

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<flight_core::FlightCoreNode>());
  rclcpp::shutdown();
  return 0;
}
