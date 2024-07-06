import time
from threading import Thread

from flask import Flask

from flask_websockets import WebSocket, WebSockets


def create_app() -> Flask:
    app = Flask(__name__)
    websockets = WebSockets(app)

    @websockets.route("/echo")
    def echo(ws: WebSocket) -> None:
        with websockets.subscribe(ws, ["time", "rec"]):
            for data in ws.iter_data():
                websockets.publish(data, ["rec"])

    def publish_to_general() -> None:
        while 1:
            websockets.publish(str(time.time()), ["time"])
            time.sleep(0.1)

    Thread(target=publish_to_general).start()
    return app


if __name__ == "__main__":
    create_app().run(host="localhost", port=6969)
