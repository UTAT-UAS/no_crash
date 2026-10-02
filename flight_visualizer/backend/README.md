# Flight visualizer backend

Placeholder for the Python backend. The container supplies Python 3.12,
venv support, pip, Python development headers, and native build tools.

Create a dedicated environment when implementation begins:

```bash
python3 -m venv ~/.venvs/flight-visualizer-backend
source ~/.venvs/flight-visualizer-backend/bin/activate
```

Declare backend dependencies in this project's dependency manifest. Choose
`--system-site-packages` when creating the venv if it needs apt-managed ROS
modules such as `rclpy`. No backend framework has been selected yet.
