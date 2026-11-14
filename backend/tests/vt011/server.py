"""Uvicorn TCP server trên loopback/cổng OS cấp, không mở ra mạng ngoài."""
from contextlib import contextmanager
import socket
from threading import Thread, Event
from time import monotonic

import uvicorn


@contextmanager
def live_server(app):
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port,
        log_level='error', lifespan='off', timeout_keep_alive=2))
    thread = Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        deadline = monotonic() + 15
        while not server.started:
            if not thread.is_alive() or monotonic() > deadline:
                raise RuntimeError('VT011 TCP server failed to start')
            Event().wait(.01)
        yield f'http://127.0.0.1:{port}'
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        sock.close()
        if thread.is_alive():
            raise RuntimeError('VT011 TCP server did not stop')
