from __future__ import annotations

import unittest

from flask import Blueprint, Flask

import flask_websockets
from flask_websockets import WebSocket


class FlaskSockTestCase(unittest.TestCase):
    def test_create_direct(self) -> None:
        app = Flask(__name__, static_folder=None)
        sock = flask_websockets.WebSockets(app)

        @sock.route("/ws")
        def ws(_ws: WebSocket) -> None:
            pass

        assert sock.app == app
        assert sock.bp is None
        assert app.url_map._rules[0].rule == "/ws"
        assert app.url_map._rules[0].websocket is True

    def test_create_indirect(self) -> None:
        app = Flask(__name__, static_folder=None)
        sock = flask_websockets.WebSockets()

        @sock.route("/ws")
        def ws(_ws: WebSocket) -> None:
            pass

        assert sock.app is None
        assert sock.bp is not None

        sock.init_app(app)

        assert sock.app is not None
        assert sock.bp is not None  # type: ignore
        assert app.url_map._rules[0].rule == "/ws"
        assert app.url_map._rules[0].websocket is True

    def test_create_blueprint(self) -> None:
        app = Flask(__name__, static_folder=None)
        bp = Blueprint("bp", __name__)

        sock = flask_websockets.WebSockets()

        @sock.route("/ws", bp=bp)
        def ws(_ws: WebSocket) -> None:
            pass

        assert sock.app is None
        assert sock.bp is None

        sock.init_app(app)
        app.register_blueprint(bp, url_prefix="/bp")

        assert sock.app is not None
        assert sock.bp is None  # type: ignore

        @sock.route("/ws")
        def ws2(_ws: WebSocket) -> None:
            pass

        assert app.url_map._rules[0].rule == "/bp/ws"
        assert app.url_map._rules[0].websocket is True
        assert app.url_map._rules[1].rule == "/ws"
        assert app.url_map._rules[1].websocket is True
