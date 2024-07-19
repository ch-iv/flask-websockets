from __future__ import annotations

import contextlib
import logging
from functools import wraps
from typing import TYPE_CHECKING, Any

from flask import Blueprint, Flask, Response, current_app, request

from .websocket import WebSocket

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable
    from wsgiref.types import StartResponse


__all__ = ("WebSockets",)


logger = logging.getLogger(__name__)


class WebSockets:
    """Instantiate the Flask-WebSockets extension.

    :param app: The Flask application instance. If not provided, it must be
                initialized later by calling the :func:`WebSockets.init_app` method.
    """

    def __init__(self, app: Flask | None = None) -> None:
        self.app: Flask | None = None
        self.bp: Blueprint | None = None
        if app is not None:
            self.app = app
            self.init_app(app)
        self._subscriptions: dict[str, set[WebSocket]] = {}

    def init_app(self, app: Flask) -> None:
        """Initialize the Flask-Socket extension.


        :param app: The Flask application instance. This method only needs to
                    be called if the application instance was not passed as
                    an argument to the constructor.
        """
        if self.bp:
            app.register_blueprint(self.bp)
        self.app = app

    def route(self, path: str, bp: Blueprint | None = None, **kwargs: Any) -> Callable[[Callable], None]:
        """Decorator to create a WebSocket route.

        The decorated function will be invoked when a WebSocket client
        establishes a connection, with a WebSocket connection object passed
        as an argument. Example::

            @websockets.route('/ws')
            def websocket_route(ws: WebSocket):
                # The ws object has the following methods:
                # - ws.send(data)
                # - ws.receive(timeout=None)
                # - ws.close(reason=None, message=None)

        If the route has variable components, the ``ws`` argument needs to be
        included before them.

        :param path: the URL associated with the route.
        :param bp: the blueprint on which to register the route. If not given,
                   the route is attached directly to the Flask application
                   instance. When a blueprint is used, the application is
                   responsible for the blueprint's registration.
        :param kwargs: additional route options. See the Flask documentation
                       for the ``app.route`` decorator for details.
        """

        def decorator(f: Callable) -> None:
            @wraps(f)
            def websocket_route(*args: Any, **options: Any) -> Response:
                ws = WebSocket(request.environ, **current_app.config.get("SOCK_SERVER_OPTIONS", {}))

                with contextlib.suppress(RuntimeError):
                    f(ws, *args, **options)
                    ws.close()

                class WebSocketResponse(Response):
                    def __call__(self, environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
                        if ws.mode == "gunicorn":
                            raise StopIteration()

                        return super().__call__(environ, start_response)

                return WebSocketResponse()

            kwargs.update({"websocket": True})

            if bp:
                bp.route(path, **kwargs)(websocket_route)
            elif self.app:
                self.app.route(path, **kwargs)(websocket_route)
            else:
                if self.bp is None:  # pragma: no branch
                    self.bp = Blueprint("__flask_sock", __name__)
                self.bp.route(path, **kwargs)(websocket_route)

        return decorator

    @contextlib.contextmanager
    def subscribe(self, ws: WebSocket, channels: Iterable[str]) -> Generator[None, None, None]:
        """Subscribes a websocket to channels. All subscribed websockets receive events from the channel they
        are subscribed to.

        Example::

            @websockets.route("/ws")
            def websocket_route(ws: WebSocket):
                with websockets.subscribe(ws, ["channel1", "channel2"]):
                    for data in ws.iter_data():
                        pass

        :param ws: A websocket to subscribe
        :param channels: Channels to subscribe the websocket to
        :return:
        """
        channels_set: set[str] = set(channels)
        for channel in channels_set:
            if channel not in self._subscriptions:
                self._subscriptions[channel] = set()
            self._subscriptions[channel].add(ws)

        yield None
        self.unsubscribe(ws, channels)

    def unsubscribe(self, ws: WebSocket, channels: Iterable[str]) -> None:
        """Unsubscribe a websocket from given channels.

        :param ws: A websocket to unsubscribe
        :param channels: Channels to unsubscribe from
        :return:
        """
        channels_set: set[str] = set(channels)
        for channel in channels_set:
            if channel in self._subscriptions:
                self._subscriptions[channel].remove(ws)

    def publish(
        self, data: Any, channels: Iterable[str], encode_json: bool = False, encode_msgpack: bool = False
    ) -> None:
        """Publish data to the given channels. All subscribed websockets will receive this data.

        :param data: Data to publish to the channels
        :param encode_json: Whether data should be json-encoded before publishing
        :param encode_msgpack: Whether data should be msgpack-encoded before publishing
        :param channels: Channels to publish the data to
        """
        channels_set: set[str] = set(channels)
        for channel in channels_set:
            if channel not in self._subscriptions:
                continue

            for ws in self._subscriptions[channel]:
                try:
                    if encode_json:
                        ws.send_json(data)
                    elif encode_msgpack:
                        ws.send_msgpack(data)
                    else:
                        ws.send(data)
                except RuntimeError:
                    logger.warning("Couldn't to send data to a socket.")
