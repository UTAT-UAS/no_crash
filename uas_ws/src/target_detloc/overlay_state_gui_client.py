import queue
import threading
import tkinter as tk
from tkinter import ttk

import rclpy
from rclpy.node import Node
from target_detloc.msg import OverlayState
from target_detloc.srv import GetOverlayState, SetOverlayState

OVERLAY_STATE_CHANGE_TOPIC = "/target_detloc/internal/overlay_state"
# Adjust namespace prefix if your server node is launched inside a namespace (e.g. "/target_detloc/set_overlay_state")
SET_SRV_NAME = "set_overlay_state"
GET_SRV_NAME = "get_overlay_state"


class OverlayStateClientNode(Node):
    def __init__(self, ui_queue: queue.Queue):
        super().__init__("overlay_state_gui_client")
        self._ui_queue = ui_queue

        self._set_client = self.create_client(SetOverlayState, SET_SRV_NAME)
        self._get_client = self.create_client(GetOverlayState, GET_SRV_NAME)
        self._state_sub = self.create_subscription(
            OverlayState,
            OVERLAY_STATE_CHANGE_TOPIC,
            self._on_state_changed,
            10,
        )

    def _post_ui(self, event_type: str, payload=None):
        self._ui_queue.put((event_type, payload))

    def _on_state_changed(self, msg: OverlayState):
        self._post_ui(
            "state_update",
            {
                "show_detection": bool(msg.show_detection),
                "show_depth_instead_of_color": bool(msg.show_depth_instead_of_color),
                "source": "topic",
            },
        )

    def fetch_state(self, timeout_sec: float = 1.0):
        if not self._get_client.service_is_ready():
            if not self._get_client.wait_for_service(timeout_sec=timeout_sec):
                self._post_ui("status", f"Service '{GET_SRV_NAME}' not available.")
                return

        req = GetOverlayState.Request()
        future = self._get_client.call_async(req)
        future.add_done_callback(self._on_get_done)

    def _on_get_done(self, future):
        try:
            resp = future.result()
        except Exception as exc:
            self._post_ui("status", f"Get failed: {exc}")
            return

        if resp is None:
            self._post_ui("status", "Get returned no response.")
            return

        if resp.success:
            self._post_ui(
                "state_update",
                {
                    "show_detection": bool(resp.show_detection),
                    "show_depth_instead_of_color": bool(resp.show_depth_instead_of_color),
                    "source": "get_srv",
                },
            )
            self._post_ui("status", "Fetched current state from server.")
        else:
            self._post_ui("status", "Server reported success=False on Get.")

    def push_state(self, show_detection: bool, show_depth_instead_of_color: bool, timeout_sec: float = 1.0):
        if not self._set_client.service_is_ready():
            if not self._set_client.wait_for_service(timeout_sec=timeout_sec):
                self._post_ui("status", f"Service '{SET_SRV_NAME}' not available.")
                return

        req = SetOverlayState.Request()
        req.show_detection = bool(show_detection)
        req.show_depth_instead_of_color = bool(show_depth_instead_of_color)

        future = self._set_client.call_async(req)
        future.add_done_callback(self._on_set_done)

    def _on_set_done(self, future):
        try:
            resp = future.result()
        except Exception as exc:
            self._post_ui("status", f"Set failed: {exc}")
            return

        if resp is None:
            self._post_ui("status", "Set returned no response.")
            return

        if resp.success:
            self._post_ui("status", "Overlay state updated on server.")
        else:
            self._post_ui("status", "Server reported success=False on Set.")


class OverlayStateGUI:
    def __init__(self, root: tk.Tk, node: OverlayStateClientNode, ui_queue: queue.Queue):
        self.root = root
        self.node = node
        self.ui_queue = ui_queue

        self.root.title("Target DetLoc - Overlay State Controller")
        self.root.resizable(False, False)

        self.show_detection_var = tk.BooleanVar(value=False)
        self.show_depth_var = tk.BooleanVar(value=False)
        self.live_detection_text = tk.StringVar(value="False")
        self.live_depth_text = tk.StringVar(value="False")
        self.status_text = tk.StringVar(value="Initializing...")

        self._build_ui()
        self._poll_ui_queue()

        # Sync initial state once GUI starts
        self.root.after(150, self.node.fetch_state)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=16)
        main.grid(row=0, column=0, sticky="nsew")

        # Controls section
        controls = ttk.LabelFrame(main, text="Overlay Controls", padding=12)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        ttk.Checkbutton(
            controls,
            text="Show Detection",
            variable=self.show_detection_var,
        ).grid(row=0, column=0, sticky="w", pady=4)

        ttk.Checkbutton(
            controls,
            text="Show Depth Instead of Color",
            variable=self.show_depth_var,
        ).grid(row=1, column=0, sticky="w", pady=4)

        btn_row = ttk.Frame(controls)
        btn_row.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        ttk.Button(btn_row, text="Apply State (Set)", command=self._on_apply_clicked).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(btn_row, text="Refresh State (Get)", command=self._on_refresh_clicked).grid(
            row=0, column=1
        )

        # Live published state readout
        live = ttk.LabelFrame(main, text="Published State (/target_detloc/internal/overlay_state)", padding=12)
        live.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        ttk.Label(live, text="show_detection:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(live, textvariable=self.live_detection_text, font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=1, sticky="w"
        )

        ttk.Label(live, text="show_depth_instead_of_color:").grid(row=1, column=0, sticky="w", padx=(0, 10))
        ttk.Label(live, textvariable=self.live_depth_text, font=("TkDefaultFont", 10, "bold")).grid(
            row=1, column=1, sticky="w"
        )

        # Status bar
        ttk.Label(main, textvariable=self.status_text, foreground="#333333").grid(
            row=2, column=0, columnspan=2, sticky="w"
        )

    def _on_apply_clicked(self):
        det = self.show_detection_var.get()
        depth = self.show_depth_var.get()
        self.status_text.set("Sending set_overlay_state request...")
        threading.Thread(
            target=self.node.push_state,
            args=(det, depth),
            daemon=True,
        ).start()

    def _on_refresh_clicked(self):
        self.status_text.set("Requesting get_overlay_state...")
        threading.Thread(
            target=self.node.fetch_state,
            daemon=True,
        ).start()

    def _apply_state_to_ui(self, data: dict):
        det = data["show_detection"]
        depth = data["show_depth_instead_of_color"]
        src = data["source"]

        self.live_detection_text.set(str(det))
        self.live_depth_text.set(str(depth))

        # Keep checkboxes synced with authoritative server/topic state
        self.show_detection_var.set(det)
        self.show_depth_var.set(depth)

        if src == "topic":
            self.status_text.set("Received state update from topic.")

    def _poll_ui_queue(self):
        try:
            while True:
                event_type, payload = self.ui_queue.get_nowait()
                if event_type == "state_update":
                    self._apply_state_to_ui(payload)
                elif event_type == "status":
                    self.status_text.set(payload)
        except queue.Empty:
            pass

        self.root.after(50, self._poll_ui_queue)


def main():
    rclpy.init()
    ui_queue = queue.Queue()
    node = OverlayStateClientNode(ui_queue)

    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    root = tk.Tk()
    OverlayStateGUI(root, node, ui_queue)

    def on_close():
        root.destroy()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    root.protocol("WM_DELETE_WINDOW", on_close)
    try:
        root.mainloop()
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()