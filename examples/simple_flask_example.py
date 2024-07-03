import time
from threading import Thread

from flask import Flask

from flask_channels import Channels, WebSocket

app = Flask(__name__)
channels = Channels(app)


@channels.route("/echo")
def echo(ws: WebSocket) -> None:
    with channels.subscribe(ws, ["time", "rec"]):
        for data in ws.iter_data():
            channels.publish(data, ["rec"])


def publish_to_general() -> None:
    while 1:
        channels.publish(str(time.time()), ["time"])
        time.sleep(0.1)


Thread(target=publish_to_general).start()
app.run(host="localhost", port=6969)
