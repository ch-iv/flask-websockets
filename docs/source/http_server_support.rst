WSGI HTTP Server Support
========================

*flask-websockets* was built with support for most popular WSGI HTTP severs in mind.

Werkzeug
++++++++

*flask-websockets* works with Werkzeug out of the box without any additional configuration. Most examples in the documentation assume usage with Werkzeug.

Gunicorn
++++++++
*flask-websockets* works with gunicorn out of the box with the gunicorn CLI or a script configuration. It is the recommended HTTP server for *flask-websockets* in production.

Eventlet
++++++++
Eventlet is supported. However due to the eventlet project being abandoned, future support for it is not planned.

Gevent
++++++
For gevent to work with *flask-websockets* it needs to be patched. Insert the following lines into your flask application as early as possible:

.. code-block:: python

    from gevent import monkey
    monkey.patch_all()

For more information see https://www.gevent.org/api/gevent.monkey.html.
