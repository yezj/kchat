from tornado.tcpclient import TCPClient
from tornado.ioloop import IOLoop
from tornado import gen
import json


class TestTcpclient(object):
    """docstring for TestTcpClient"""

    def __init__(self, host, port):
        self.host = host
        self.port = port

    @gen.coroutine
    def start(self):
        self.stream = yield TCPClient().connect(self.host, self.port)
        print json.dumps(dict(msg='create_room', user=1, room_id='1'))
        self.stream.write(json.dumps(dict(msg='create_room', uid=1, room_id='1')))
        self.stream.write('\n')
        rec = yield self.stream.read_until('/n')
        print 'recive from the server', rec


def test_main():
    tcp_client = TestTcpclient('127.0.0.1', '8888')
    tcp_client.start()
    IOLoop.instance().start()


test_main()
