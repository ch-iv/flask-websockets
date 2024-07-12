from __future__ import annotations

import platform
import time
from queue import Queue
from typing import cast

import requests
from flask import Flask, Response, make_response, request
from websocket import create_connection

from flask_websockets import WebSocket, WebSockets
from flask_websockets.websocket import AbstractSocket

if platform.system() == "Darwin":  # macOS
    from multiprocess.context import Process  # type: ignore
else:
    from multiprocessing import Process


class MockClient:
    def __init__(self, endpoint: str) -> None:
        self.ws: AbstractSocket = cast(AbstractSocket, create_connection(endpoint))
        self.msg_history: list[str | bytes] = []

    def close(self) -> None:
        self.ws.close()


class MockServer:
    def __init__(self) -> None:
        self.queue: Queue[str | bytes] = Queue()
        self.app = Flask(__name__)
        self.websockets = WebSockets(self.app)
        self.server_process: Process | None = None

        @self.websockets.route("/echo")
        def echo(ws: WebSocket) -> None:
            for data in ws.iter_data():
                ws.send(data)

        @self.websockets.route("/subscribe")
        def subscribe(ws: WebSocket) -> None:
            channel = request.args.get("channel", default="", type=str)
            with self.websockets.subscribe(ws, [channel]):
                time.sleep(1000)

        @self.app.route("/publish")
        def publish() -> Response:
            data = request.args.get("data", default="", type=str)
            channel = request.args.get("channel", default="", type=str)
            self.websockets.publish(data, [channel])
            return make_response()

    def run(self) -> None:
        self.server_process = Process(target=lambda: self.app.run(host="localhost", port=6969))
        self.server_process.start()

    def shutdown(self) -> None:
        if self.server_process is not None:
            self.server_process.terminate()
            self.server_process.join()


def send_command(client: MockClient, data: str | bytes) -> None:
    client.ws.send(data)


def assert_response(client: MockClient, expected_resp: str | bytes) -> None:
    resp = client.ws.recv()
    assert resp == expected_resp


def close_command(client: MockClient) -> None:
    client.ws.close()


def await_response(client: MockClient) -> None:
    resp = client.ws.recv()
    client.msg_history.append(resp)


def publish_command(channel: str, data: str) -> None:
    requests.get(f"http://localhost:6969/publish?data={data}&channel={channel}", timeout=5)


def test_mock_client() -> None:
    if platform.system() != "Linux":
        return

    s = MockServer()
    s.run()

    # waiting unit the server is ready to accept connections
    # should be replaced with a some kind of hook to the server
    time.sleep(0.5)

    c1 = MockClient("ws://localhost:6969/echo")
    c2 = MockClient("ws://localhost:6969/echo")

    send_command(c1, "hello from 1")
    assert_response(c1, "hello from 1")

    send_command(c2, "hello from 2")
    assert_response(c2, "hello from 2")

    c1.close()
    c2.close()

    c1 = MockClient("ws://localhost:6969/subscribe?channel=test")
    c2 = MockClient("ws://localhost:6969/subscribe?channel=test")

    publish_command("test", "hello from test")
    assert_response(c1, "hello from test")
    assert_response(c2, "hello from test")

    c1.close()
    c2.close()
    s.shutdown()
