
#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError

import cv2
import numpy as np


DEPTH_TOPIC = "/target_detloc/internal/depth"
COLOR_TOPIC = "/target_detloc/internal/color"


class FrameVisualizer(Node):

    def __init__(self):
        super().__init__("frame_visualizer")

        self.bridge = CvBridge()

        self.depth_image = None
        self.color_image = None

        self.depth_sub = self.create_subscription(
            Image,
            DEPTH_TOPIC,
            self.depth_callback,
            10
        )

        self.color_sub = self.create_subscription(
            Image,
            COLOR_TOPIC,
            self.color_callback,
            10
        )

        # Display timer: 30 FPS
        self.timer = self.create_timer(
            1.0 / 30.0,
            self.display_images
        )

        cv2.namedWindow(
            "Depth Image",
            cv2.WINDOW_NORMAL
        )

        cv2.namedWindow(
            "Color Image",
            cv2.WINDOW_NORMAL
        )

        self.get_logger().info("Frame visualizer started")
        self.get_logger().info(f"Depth topic: {DEPTH_TOPIC}")
        self.get_logger().info(f"Color topic: {COLOR_TOPIC}")

    def depth_callback(self, msg):

        try:
            self.get_logger().debug(
                f"Depth encoding: {msg.encoding}"
            )

            # Preserve original 16-bit values
            self.depth_image = self.bridge.imgmsg_to_cv2(
                msg,
                desired_encoding="passthrough"
            )

        except CvBridgeError as e:
            self.get_logger().error(
                f"Depth conversion error: {e}"
            )

    def color_callback(self, msg):

        try:
            self.get_logger().debug(
                f"Color encoding: {msg.encoding}"
            )

            # Convert to RGB8
            self.color_image = self.bridge.imgmsg_to_cv2(
                msg,
                desired_encoding="rgb8"
            )

        except CvBridgeError as e:
            self.get_logger().error(
                f"Color conversion error: {e}"
            )

    def display_images(self):

        # ---------------------------
        # Display depth image
        # ---------------------------

        if self.depth_image is not None:

            depth = self.depth_image
            print(depth)

            # Convert 16-bit depth into 8-bit visualization
            # Original depth data remains unchanged.
            valid = np.isfinite(depth) & (depth > 0)

            depth_display = np.zeros(
                depth.shape,
                dtype=np.uint8
            )

            if np.any(valid):
                min_val = np.min(depth[valid])
                max_val = np.max(depth[valid])

                if max_val > min_val:
                    depth_display[valid] = (
                        (depth[valid] - min_val)
                        * 255.0
                        / (max_val - min_val)
                    ).astype(np.uint8)
                    depth_display[depth_display != 0] = 1
                    depth_display[depth_display == 0] = 255

            depth_display = cv2.applyColorMap(
                depth_display,
                cv2.COLORMAP_OCEAN
            )

            cv2.imshow(
                "Depth Image",
                depth_display
            )

        # ---------------------------
        # Display color image
        # ---------------------------

        if self.color_image is not None:

            # OpenCV uses BGR, while ROS image is RGB8
            color_bgr = cv2.cvtColor(
                self.color_image,
                cv2.COLOR_RGB2BGR
            )

            cv2.imshow(
                "Color Image",
                color_bgr
            )

        cv2.waitKey(1)

    def destroy_node(self):

        cv2.destroyAllWindows()
        super().destroy_node()


def main(args=None):

    rclpy.init(args=args)

    node = FrameVisualizer()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

