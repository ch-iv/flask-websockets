from gevent import monkey
from gevent.pywsgi import WSGIServer
from simple_flask_example import create_app

monkey.patch_all()


app = create_app()
http_server = WSGIServer(("127.0.0.1", 6969), app)
http_server.serve_forever()
