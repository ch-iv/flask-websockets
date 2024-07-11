import json
import random
from typing import NamedTuple

from flask import Flask, render_template, session

from flask_websockets import WebSocket, WebSockets

app = Flask(__name__)
app.secret_key = "super secret key"  # noqa: S105
websockets = WebSockets(app)


class JoinMessage(NamedTuple):
    username: str
    message_type: str = "user_join"

    def __str__(self):
        return json.dumps(
            {
                "message_type": self.message_type,
                "username": self.username,
            }
        )


class LeaveMessage(NamedTuple):
    username: str
    message_type: str = "user_leave"

    def __str__(self):
        return json.dumps(
            {
                "message_type": self.message_type,
                "username": self.username,
            }
        )


class SendMessage(NamedTuple):
    sender: str
    content: str
    message_type: str = "send"

    def __str__(self):
        return json.dumps({"message_type": self.message_type, "sender": self.sender, "content": self.content})


def generate_username() -> str:
    first_word = ["Yapping", "Glamorous", "Rizzful", "Unlucky", "Gawking"]
    second_word = ["Turtle", "Mouse", "Bard", "Computer", "Hawk"]

    return random.sample(first_word, 1)[0] + random.sample(second_word, 1)[0] + str(random.randint(1000, 9999))  # noqa: S311


@websockets.route("/chat")
def chat(ws: WebSocket) -> None:
    username: str | None = session.get("username")

    if username is None:
        return

    with websockets.subscribe(ws, ["chat"]):
        websockets.publish(str(JoinMessage(username=username)), ["chat"])

        for data in ws.iter_text():
            websockets.publish(str(SendMessage(sender=username, content=data)), ["chat"])

    websockets.publish(str(LeaveMessage(username=username)), ["chat"])


@app.route("/")
def index():
    session["username"] = generate_username()
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="localhost", port=6969)
