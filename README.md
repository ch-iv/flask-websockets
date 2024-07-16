# flask-websockets
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ch-iv/flask-websockets/ci.yml?style=flat&logo=github&label=Tests%20%26%20Linting)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ch-iv/flask-websockets/publish.yml?style=flat&logo=github&label=Latest%20Release)
[![Documentation Status](https://readthedocs.org/projects/flaskwebsockets/badge/?version=latest)](https://flaskwebsockets.readthedocs.io/en/latest/?badge=latest)
![PyPI - Downloads](https://img.shields.io/pypi/dm/flask-websockets)
[![linting - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json&labelColor=202235)](https://github.com/astral-sh/ruff)
[![code style - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/format.json&labelColor=202235)](https://github.com/astral-sh/ruff)

flask-websockets is an extension library for Flask, a popular web micro-framework. It adds real-time communication capabilities to your Flask application. flask-websockets implements the WebSocket protocol and allows for low-level control over the connections, as well as a high-level API for subscribing connections to rooms.

flask-websockets supports most popular HTTP WSGI servers such as Werkzeug, Gunicorn, Eventlet and Gevent.

## Example Usage
```python
import time
from threading import Thread
from flask import Flask
from flask_websockets import WebSocket, WebSockets

app = Flask(__name__)
websockets = WebSockets(app)


@websockets.route("/ws")
def websocket_route(ws: WebSocket) -> None:
    with websockets.subscribe(ws, ["server_time"]):
        for data in ws.iter_data():    # keep listening to the websocket so it doesn't disconnect
            pass


def publish_server_time() -> None:
    while True:
        websockets.publish(str(time.time()), ["server_time"])
        time.sleep(1)


Thread(target=publish_server_time).start()
app.run(host="localhost", port=6969)
```
