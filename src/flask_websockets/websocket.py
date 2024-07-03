from __future__ import annotations

import contextlib
import enum
import selectors
from abc import ABC, abstractmethod
from time import time
from typing import IO, TYPE_CHECKING, Any, cast

from wsproto import ConnectionType, WSConnection
from wsproto.events import (
    AcceptConnection,
    BytesMessage,
    CloseConnection,
    Message,
    Ping,
    Pong,
    Request,
    TextMessage,
)
from wsproto.extensions import PerMessageDeflate
from wsproto.frame_protocol import CloseReason

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = (
    "AbstractSocket",
    "WebSocket",
    "WebSocketState",
)


class AbstractSocket(ABC, IO):
    @abstractmethod
    def send(self, data: Any) -> None:
        pass

    @abstractmethod
    def recv(self, num_bytes: int) -> bytes:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class WebSocketState(enum.Enum):
    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2
    RESPONSE = 3


class WebSocket:
    def __init__(
        self,
        environ: dict,
        subprotocols: list[str] | str | None = None,
        receive_bytes: int = 4096,
        ping_interval: int | None = None,
        max_message_size: int = 1_000_000_000,
        thread_class: Any = None,
        event_class: Any = None,
        selector_class: Any = None,
    ) -> None:
        self.environ = environ
        self.subprotocol = None
        self.receive_bytes = receive_bytes
        self.ping_interval = ping_interval
        self.max_message_size = max_message_size
        self.pong_received = True
        self.input_buffer: list[str | bytes] = []
        self.incoming_message = bytearray()
        self.incoming_message_len = 0
        self.close_reason = CloseReason.NO_STATUS_RCVD
        self.close_message = None
        self.state = WebSocketState.CONNECTING
        self.subprotocols = subprotocols or []
        if isinstance(self.subprotocols, str):
            self.subprotocols = [self.subprotocols]

        if thread_class is None:
            import threading

            thread_class = threading.Thread
        if event_class is None:
            import threading

            event_class = threading.Event
        if selector_class is None:
            selector_class = selectors.DefaultSelector
        self.selector_class = selector_class
        self.event = event_class()

        self.mode = "unknown"
        sock = None
        if "werkzeug.socket" in environ:
            sock = environ.get("werkzeug.socket")
            self.mode = "werkzeug"
        elif "gunicorn.socket" in environ:
            sock = environ.get("gunicorn.socket")
            self.mode = "gunicorn"
        elif "eventlet.input" in environ:
            eventlet_input = environ.get("eventlet.input")
            assert eventlet_input is not None
            sock = eventlet_input.get_socket()
            self.mode = "eventlet"
        elif environ.get("SERVER_SOFTWARE", "").startswith("gevent"):
            wsgi_input = environ["wsgi.input"]
            if not hasattr(wsgi_input, "raw") and hasattr(wsgi_input, "rfile"):
                wsgi_input = wsgi_input.rfile
            if hasattr(wsgi_input, "raw"):
                sock = wsgi_input.raw._sock
                with contextlib.suppress(NotImplementedError):
                    sock = sock.dup()
                self.mode = "gevent"

        if sock is None:
            raise RuntimeError("Cannot obtain socket from WSGI environment.")

        self.sock: AbstractSocket = sock
        self.thread = thread_class(target=self._thread)
        self.thread.name = self.thread.name.replace("(_thread)", "(flask_websockets.WebSocket._thread)")
        self.thread.start()

        self.ws = WSConnection(ConnectionType.SERVER)
        self.handshake()

    def send_bytes(self, data: bytes) -> None:
        self._send(self.ws.send(BytesMessage(data=data)))

    def send_text(self, data: str) -> None:
        assert isinstance(data, str)
        self._send(self.ws.send(TextMessage(data=data)))

    def _send(self, message_bytes: bytes) -> None:
        if self.state == WebSocketState.DISCONNECTED:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')

        self.sock.send(message_bytes)

    def receive(self, timeout: int | None = None) -> bytes | str | None:
        """Receive data over the WebSocket connection.

        :param timeout: Amount of time to wait for the data, in seconds. Set
                        to ``None`` (the default) to wait indefinitely. Set
                        to 0 to read without blocking.

        The data received is returned, as ``bytes`` or ``str``, depending on
        the type of the incoming message.
        """
        while self.state == WebSocketState.CONNECTED and not self.input_buffer:
            if not self.event.wait(timeout=timeout):
                return None
            self.event.clear()

        try:
            return self.input_buffer.pop(0)
        except IndexError:
            pass

        if not self.state == WebSocketState.CONNECTED:  # pragma: no cover
            raise RuntimeError()

        return None

    def close(self, code: int = CloseReason.NORMAL_CLOSURE, reason: str | None = None) -> None:
        """Close the WebSocket connection.

        :param code: A numeric status code indicating the reason of the
                       closure, as defined by the WebSocket specification. The
                       default is 1000 (normal closure).
        :param reason: A text message to be sent to the other side.
        """
        if self.state == WebSocketState.DISCONNECTED:
            raise RuntimeError('Cannot call "close" once a close message has been sent.')

        close_message = self.ws.send(CloseConnection(code, reason))

        self.sock.send(close_message)

        self.state = WebSocketState.DISCONNECTED

    def _thread(self) -> None:
        selector = self.selector_class()
        next_ping = 0

        if self.ping_interval:
            next_ping = int(time()) + self.ping_interval
            selector.register(self.sock, selectors.EVENT_READ, True)

        while self.state != WebSocketState.DISCONNECTED:
            if self.ping_interval:
                now = int(time())
                if next_ping <= now or not selector.select(next_ping - now):
                    if not self.pong_received:
                        self.close(
                            code=CloseReason.POLICY_VIOLATION,
                            reason="Ping/Pong timeout",
                        )
                        break

                    self.pong_received = False
                    self.sock.send(self.ws.send(Ping()))
                    next_ping = max(now, next_ping) + self.ping_interval
                    continue

            in_data = self.sock.recv(self.receive_bytes)
            self.ws.receive_data(in_data)
            self._handle_events()

        selector.close()
        self.sock.close()

    def _handle_events(self) -> None:
        for event in self.ws.events():
            if isinstance(event, Request):
                accept_message = self.ws.send(
                    AcceptConnection(
                        subprotocol=self.choose_subprotocol(event),
                        extensions=[PerMessageDeflate()],
                    )
                )
                self.sock.send(accept_message)

            elif isinstance(event, CloseConnection):
                self.sock.send(self.ws.send(event.response()))
                self.state = WebSocketState.DISCONNECTED
                self.event.set()

            elif isinstance(event, Ping):
                self.sock.send(self.ws.send(event.response()))

            elif isinstance(event, Pong):
                self.pong_received = True

            elif isinstance(event, TextMessage | BytesMessage):
                self.incoming_message_len += len(event.data)

                if self.incoming_message_len > self.max_message_size:
                    self.close(CloseReason.MESSAGE_TOO_BIG, "Message is too big")
                    return

                if isinstance(event, TextMessage):
                    self.incoming_message += event.data.encode()
                else:
                    self.incoming_message += event.data

                event = cast(Message, event)
                if not event.message_finished:
                    continue

                if isinstance(event, BytesMessage):
                    self.input_buffer.append(bytes(self.incoming_message))
                elif isinstance(event, TextMessage):
                    self.input_buffer.append(self.incoming_message.decode())

                self.incoming_message = bytearray()
                self.incoming_message_len = 0
                self.event.set()

    @classmethod
    def accept(
        cls,
        environ: dict,
        subprotocols: list[str] | str | None = None,
        receive_bytes: int = 4096,
        ping_interval: Any = None,
        max_message_size: int = 1_000_000_000,
        thread_class: Any = None,
        event_class: Any = None,
        selector_class: Any = None,
    ) -> WebSocket:
        """Accept a WebSocket connection from a client.

        :param environ: A WSGI ``environ`` dictionary with the request details.
                        Among other things, this class expects to find the
                        low-level network socket for the connection somewhere
                        in this dictionary. Since the WSGI specification does
                        not cover where or how to store this socket, each web
                        server does this in its own different way. Werkzeug,
                        Gunicorn, Eventlet and Gevent are the only web servers
                        that are currently supported.
        :param subprotocols: A list of supported subprotocols, or ``None`` (the
                             default) to disable subprotocol negotiation.
        :param receive_bytes: The size of the receive buffer, in bytes. The
                              default is 4096.
        :param ping_interval: Send ping packets to clients at the requested
                              interval in seconds. Set to ``None`` (the
                              default) to disable ping/pong logic. Enable to
                              prevent disconnections when the line is idle for
                              a certain amount of time, or to detect
                              unresponsive clients and disconnect them. A
                              recommended interval is 25 seconds.
        :param max_message_size: The maximum size allowed for a message, in
                                 bytes, or ``None`` for no limit. The default
                                 is ``None``.
        :param thread_class: The ``Thread`` class to use when creating
                             background threads. The default is the
                             ``threading.Thread`` class from the Python
                             standard library.
        :param event_class: The ``Event`` class to use when creating event
                            objects. The default is the `threading.Event``
                            class from the Python standard library.
        :param selector_class: The ``Selector`` class to use when creating
                               selectors. The default is the
                               ``selectors.DefaultSelector`` class from the
                               Python standard library.
        """
        return cls(
            environ,
            subprotocols=subprotocols,
            receive_bytes=receive_bytes,
            ping_interval=ping_interval,
            max_message_size=max_message_size,
            thread_class=thread_class,
            event_class=event_class,
            selector_class=selector_class,
        )

    def handshake(self) -> None:
        in_data = b"GET / HTTP/1.1\r\n"
        for key, value in self.environ.items():
            if key.startswith("HTTP_"):
                header = "-".join([p.capitalize() for p in key[5:].split("_")])
                in_data += f"{header}: {value}\r\n".encode()
        in_data += b"\r\n"

        self.state = WebSocketState.CONNECTED
        self.ws.receive_data(in_data)
        self._handle_events()

    def choose_subprotocol(self, request: Request) -> str | None:
        """Choose a subprotocol to use for the WebSocket connection.

        The default implementation selects the first protocol requested by the
        client that is accepted by the server. Subclasses can override this
        method to implement a different subprotocol negotiation algorithm.

        :param request: A ``Request`` object.

        The method should return the subprotocol to use, or ``None`` if no
        subprotocol is chosen.
        """
        for subprotocol in request.subprotocols:
            if subprotocol in self.subprotocols:
                return subprotocol
        return None

    def iter_data(self) -> Iterator[str | bytes]:
        try:
            while True:
                data = self.receive()
                if data is None:
                    continue
                yield data
        except RuntimeError:
            pass
