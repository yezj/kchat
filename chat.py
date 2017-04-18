#!/usr/bin/env python
# coding=utf-8
import uuid
import conf
import time
import simplejson as json
from struct import unpack
from tornado.tcpserver import TCPServer
from tornado.ioloop import IOLoop
from tornado.options import options, parse_config_file, parse_command_line
from mongoengine import connect


class Connection(object):
    _conns = set()
    _buffer = b''

    def __init__(self, server, stream, address):
        # Connection._conns.add(self)
        self.open(self)
        self.__rh = RoomHandler
        self._server = server
        self._stream = stream
        self._address = address
        self._stream.set_close_callback(self.on_close)
        self.read_message()
        self.rooms = {}
        print address, "A new user has entered the chat room."

    def open(self, client):
        print 'self._conns', self._conns
        self.authenticated = False
        self._conns.add(client)

    def read_message(self):
        self._stream.read_until('\n', self.on_messages)

    def on_messages(self, data):
        # self._buffer = self._buffer + data
        # print 'buffer', self._buffer
        # if len(self._buffer) >= 4:
        #     # header部分，按大字节序转int，获取body长度
        #     length, = unpack(">I", self._buffer[0:4])
        #     print 'length', length
        #     # 如果body接收完整
        #     if len(self._buffer) >= 4 + length:
        #         # body部分，protobuf字节码
        #         packet = self._buffer[4:4 + length]
        #         print 'packet', packet
        #         # protobuf字节码转成Student对象
        #         # student = StudentMsg_pb2.Student()
        #         # student.ParseFromString(packet)
        #
        #         # 调用protobufReceived传入Student对象
        #         #self.protobufReceived(student)
        #
        #         # 去掉_buffer中已经处理的消息部分
        #         self._buffer = self._buffer[4 + length:]
        #         print 11111, self._buffer
        msg = json.loads(data)
        msg_type = msg['msg']
        print 'msg_type', msg_type
        # if not self.authenticated and msg_type != 'auth':
        #     self.send_error('authentication required')
        #     return

        if msg_type == 'auth':
            self.handle_auth(msg)
            return
        elif msg_type == 'join_room':
            # ... other handlers
            pass
        elif msg_type == 'create_room':
            self.__rh.create_room(self, self._conns, self._server.db, msg)
            pass

    def handle_auth(self, msg):
        # user_id = decrypt_token(msg['token'])
        user_id = 1
        if user_id is None:
            self.send_error('invalid token')
            return
        self.authenticated = True
        self.send_room_list()

    def send_message(self, data):
        self._stream.write(data)

    def on_close(self):
        print self._address, "A user has left the chat room."
        self._conns.remove(self)


class RoomHandler(object):
    """Store data about connections, rooms, which users are in which rooms, etc."""

    def __init__(self):
        self.client_info = {}  # for each client id we'll store  {'wsconn': wsconn, 'room':room, 'nick':nick}
        self.room_info = {}  # dict  to store a list of  {'cid':cid, 'nick':nick , 'wsconn': wsconn} for each room
        self.roomates = {}  # store a set for each room, each contains the connections of the clients in the room.

    @staticmethod
    def create_room(self, conns, db, msg):
        print conns, db, msg
        users = msg['users']
        #db.room.insert({'room_id': 'room_' + '_'.join([str(u) for u in users]), 'users': users, 'created_time': int(time.time())})


    def add_roomnick(self, room, nick):
        """Add nick to room. Return generated clientID"""
        # meant to be called from the main handler (page where somebody indicates a nickname and a room to join)
        cid = uuid.uuid4().hex  # generate a client id.
        if not room in self.room_info:  # it's a new room
            self.room_info[room] = []
        c = 1
        nn = nick
        nir = self.nicks_in_room(room)
        while True:
            if nn in nir:
                nn = nick + str(c)
            else:
                break
            c += 1

        self.client_info[cid] = {'room': room, 'nick': nn}  # we still don't know the WS connection for this client
        self.room_info[room].append({'cid': cid, 'nick': nn})
        return cid

    def add_client_conn(self, client_id, conn):
        """Store the websocket connection corresponding to an existing client."""
        self.client_info[client_id]['wsconn'] = conn
        cid_room = self.client_info[client_id]['room']

        if cid_room in self.roomates:
            self.roomates[cid_room].add(conn)
        else:
            self.roomates[cid_room] = {conn}
        print 1111, self.room_info[cid_room]
        for user in self.room_info[cid_room]:
            if user['cid'] == client_id:
                user['wsconn'] = conn
                break
        # send "join" and and "nick_list" messages
        self.send_join_msg(client_id)
        nick_list = self.nicks_in_room(cid_room)
        cwsconns = self.roomate_cwsconns(client_id)
        self.send_nicks_msg(cwsconns, nick_list)

    def remove_client(self, client_id):
        """Remove all client information from the room handler."""
        cid_room = self.client_info[client_id]['room']
        nick = self.client_info[client_id]['nick']
        # first, remove the client connection from the corresponding room in self.roomates
        client_conn = self.client_info[client_id]['wsconn']
        if client_conn in self.roomates[cid_room]:
            self.roomates[cid_room].remove(client_conn)
            if len(self.roomates[cid_room]) == 0:
                del (self.roomates[cid_room])
        r_cwsconns = self.roomate_cwsconns(client_id)
        # filter out the list of connections r_cwsconns to remove clientID
        r_cwsconns = [conn for conn in r_cwsconns if conn != self.client_info[client_id]['wsconn']]
        self.client_info[client_id] = None
        for user in self.room_info[cid_room]:
            if user['cid'] == client_id:
                self.room_info[cid_room].remove(user)
                break
        self.send_leave_msg(nick, r_cwsconns)
        nick_list = self.nicks_in_room(cid_room)
        self.send_nicks_msg(r_cwsconns, nick_list)
        if len(self.room_info[cid_room]) == 0:  # if room is empty, remove.
            del (self.room_info[cid_room])
            print "Removed empty room %s" % cid_room

    def nicks_in_room(self, rn):
        """Return a list with the nicknames of the users currently connected to the specified room."""
        nir = []  # nicks in room
        for user in self.room_info[rn]:
            nir.append(user['nick'])
        return nir

    def roomate_cwsconns(self, cid):
        """Return a list with the connections of the users currently connected to the room where
        the specified client (cid) is connected."""
        cid_room = self.client_info[cid]['room']
        r = []
        if cid_room in self.roomates:
            r = self.roomates[cid_room]
        return r

    def send_join_msg(self, client_id):
        """Send a message of type 'join' to all users connected to the room where client_id is connected."""
        nick = self.client_info[client_id]['nick']
        r_cwsconns = self.roomate_cwsconns(client_id)
        msg = {"msgtype": "join", "username": nick, "payload": " joined the chat room."}
        pmessage = json.dumps(msg)
        for conn in r_cwsconns:
            conn.write_message(pmessage)

    @staticmethod
    def send_nicks_msg(conns, nick_list):
        """Send a message of type 'nick_list' (contains a list of nicknames) to all the specified connections."""
        msg = {"msgtype": "nick_list", "payload": nick_list}
        pmessage = json.dumps(msg)
        for c in conns:
            c.write_message(pmessage)

    @staticmethod
    def send_leave_msg(nick, rconns):
        """Send a message of type 'leave', specifying the nickname that is leaving, to all the specified connections."""
        msg = {"msgtype": "leave", "username": nick, "payload": " left the chat room."}
        pmessage = json.dumps(msg)
        for conn in rconns:
            conn.write_message(pmessage)


class ChatServer(TCPServer):
    def __init__(self, *args, **kwargs):
        db = self.set_up_db(conf.mongodb_host)
        self.db = db
        super(ChatServer, self).__init__(*args, **kwargs)

    @staticmethod
    def set_up_db(host):
        logging.info("Connecting to database %s ...", host)
        client = connect('chat', host=host)
        # client['admin'].authenticate('root', 'qwer1234')
        logging.info("Database connected. Seems good.")
        return client

    def handle_stream(self, stream, address):
        Connection(self, stream, address)


if __name__ == '__main__':
    print "begin..."
    import logging

    logging.getLogger().setLevel(logging.DEBUG)
    server = ChatServer()
    server.listen(8888)
    IOLoop.instance().start()
