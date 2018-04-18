"""
WSGI config for identipy_server project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

import os
import logging, sys
#logging.basicConfig(stream=sys.stderr)
from django.conf import settings
import logging.handlers
import SocketServer as socketserver
import threading
import socket
import pickle
import struct
logger = logging.getLogger(__name__)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "identipy_server.settings")

def _socket_listener_worker(port, handler):
    try:
        tcpserver = LogRecordSocketReceiver(port=port, handler=handler)
    except socket.error as e:
        logger.error('Couldn\'t start TCP server: %s', e)
        return
    if port == 0:
        port = tcpserver.socket.getsockname()[1]
    tcpserver.serve_until_stopped()

def get_handler(handler_name):
    handler_dict = settings.LOGGING['handlers'][handler_name]
    if handler_dict['class'] == 'logging.NullHandler':
        return
    if handler_dict['class'] != 'logging.FileHandler':
        raise NotImplementedError('Non-file logging not yet supported for IdentiPy')
    log_format = settings.LOGGING['formatters'][handler_dict['formatter']]['format']
    formatter = logging.Formatter(log_format)
    supported_kw = {'filename', 'mode', 'encoding', 'delay'}
    kw = {k: v for k, v in handler_dict.items() if k in supported_kw}
    handler = logging.FileHandler(**kw)
    handler.setFormatter(formatter)
    return handler

class LogRecordStreamHandler(socketserver.StreamRequestHandler):
    """Handler for a streaming logging request."""

    def __init__(self, *args, **kwargs):
        socketserver.StreamRequestHandler.__init__(self, *args, **kwargs)

    def handle(self):
        """
        Handle multiple requests - each expected to be a 4-byte length,
        followed by the LogRecord in pickle format. Logs the record
        according to whatever policy is configured locally.
        """
        while True:
            chunk = self.connection.recv(4)
            if len(chunk) < 4:
                break
            slen = struct.unpack('>L', chunk)[0]
            chunk = self.connection.recv(slen)
            while len(chunk) < slen:
                chunk = chunk + self.connection.recv(slen - len(chunk))
            obj = self.unPickle(chunk)
            record = logging.makeLogRecord(obj)
            self.handleLogRecord(record)

    def unPickle(self, data):
        return pickle.loads(data)

    def handleLogRecord(self, record):
        self._record_handler.handle(record)

class IdentiPyHandler(LogRecordStreamHandler):
    _record_handler = get_handler('identipy_file')

class MPScoreHandler(LogRecordStreamHandler):
    _record_handler = get_handler('mpscore_file')

class LogRecordSocketReceiver(socketserver.ThreadingTCPServer):
    """
    Simple TCP socket-based logging receiver suitable for testing.
    """

    allow_reuse_address = True

    def __init__(self, host='localhost',
                 port=logging.handlers.DEFAULT_TCP_LOGGING_PORT,
                 handler=LogRecordStreamHandler):
        socketserver.ThreadingTCPServer.__init__(self, (host, port), handler)
        self.abort = 0
        self.timeout = 1
        self.logname = None

    def serve_until_stopped(self):
        import select
        abort = 0
        while not abort:
            rd, wr, ex = select.select([self.socket.fileno()], [], [], self.timeout)
            if rd:
                self.handle_request()
            abort = self.abort

# init IdentiPy logging
t = threading.Thread(target=_socket_listener_worker,
        args=(settings.LOGGING['handlers']['ipy_socket']['port'], IdentiPyHandler),
        name='identipy-listener')
t.start()
logger.info('IdentiPy logging initiated.')

# init MP score logging
t = threading.Thread(target=_socket_listener_worker,
        args=(settings.LOGGING['handlers']['mp_socket']['port'], MPScoreHandler),
        name='mpscore-listener')
t.start()
logger.info('MP-score logging initiated.')


from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
