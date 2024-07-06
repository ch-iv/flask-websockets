Getting started
===============

*flask-websockets* is an extension library for Flask, a popular web micro-framework. It adds real-time communication capabilities to your Flask application. *flask-websockets* implements the WebSocket protocol and allows for low-level control over the connections, as well as a high-level API for subscribing connections to rooms.

----

Installation
++++++++++++

flask-websockets can be installed using *pip*.

.. code-block:: bash

    pip install flask-websockets


Creating a WebSocket route
++++++++++++++++++++++++++

Once you have installed *flask-websockets* it is time to create a WebSocket route. It is an endpoint which the clients will use to establish a connection to the server.

.. code-block:: python

    from flask import Flask
    from flask_websockets import WebSockets

    app = Flask(__name__)
    websockets = WebSockets(app)

    @websockets.route("/ws")
    def websocket_route(ws: WebSocket) -> None:
        pass

    app.run(host="localhost", port=6969)

Upon running this program, Flask will spin up an endpoint, which clients can connect to at ``ws://localhost:6969/ws``. Our route doesn't do much. In fact any client connecting to it will be disconnected, since we are not doing anything with the websocket.

Sending and receiving data
++++++++++++++++++++++++++

Here is an example of a route that receives data from a websocket and sends that data back to the client.

.. code-block:: python
    :emphasize-lines: 3-4

    @websockets.route("/ws")
    def websocket_route(ws: WebSocket) -> None:
        for data in ws.iter_data():
            ws.send_bytes(data)

``ws.iter_data()`` creates an iterator, allowing us to go through the incoming messages one-by-one using a for-loop. The `data` variable contains the received data and `ws.send_bytes(data)` sends that data back to the client. Once the client disconnects, the for-loop will stop iteration.

.. note::
    ``ws.iter_data()`` will block until data is received or the client disconnects. Additionally, breaking the loop will disconnect the client.

Managing multiple connections with channels
+++++++++++++++++++++++++++++++++++++++++++

There is often a need to send messages to multiple clients simultaneously. *flask-websockets* has a high-level API to simplify this task. **Channels** are a way to group clients by a common intent. When a message is published to a channel, it is then sent to every websocket subscribed to that channel. A websocket can be subscribed to one or more channels while it is connected to the server.

.. code-block:: python
    :emphasize-lines: 3-5

    @websockets.route("/ws")
    def websocket_route(ws: WebSocket) -> None:
        with websockets.subscribe(ws, ["server_time"]):
            for data in ws.iter_data():    # keep listening to the websocket so it doesn't disconnect
                pass


``websockets.subscribe(ws, ["server_time"])`` subscribes the websocket to the ``"server_time"`` channel. The ``with`` context block is used to unsubscribe the websocket from the channels once we exit the context.

We can then publish data to the channel. Often you will want to create a separate thread to do that. In our case, we want to continuously report the current server time.

.. code-block:: python

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

In the above example, all clients connected to the ``/ws`` endpoint, will continuously receive messages containing the current server time.
