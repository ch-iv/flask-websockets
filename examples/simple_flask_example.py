import time
from threading import Thread

from flask import Flask

from flask_websockets import WebSocket, WebSockets


def create_app() -> Flask:
    app = Flask(__name__)
    websockets = WebSockets(app)

    @websockets.route("/echo")
    def echo(ws: WebSocket) -> None:
        with websockets.subscribe(ws, ["time", "echo"]):
            for data in ws.iter_data():
                websockets.publish(data, ["echo"])

    def publish_to_general() -> None:
        while 1:
            websockets.publish({"time": time.time()}, ["time"], encode_json=True)
            websockets.publish({"time": time.time()}, ["time"], encode_msgpack=True)
            time.sleep(1)

    Thread(target=publish_to_general).start()
    return app


if __name__ == "__main__":
    create_app().run(host="localhost", port=6969)
