# coding=utf-8
import socket
import sys
import json
from struct import pack

HOST = '127.0.0.1'  # The remote host
PORT = 8888  # The same port as used by the server
s = None
for res in socket.getaddrinfo(HOST, PORT, socket.AF_UNSPEC, socket.SOCK_STREAM):
    af, socktype, proto, canonname, sa = res
    try:
        s = socket.socket(af, socktype, proto)
    except socket.error, msg:
        s = None
        continue
    try:
        s.connect(sa)
    except socket.error, msg:
        s.close()
        s = None
        continue
    break
if s is None:
    print 'could not open socket'
    sys.exit(1)
auth_msg = {'msg': 'auth', 'uid': 1, 'title': '', 'tag': '', 'type': 'room'}
s.sendall(json.dumps(auth_msg))
s.sendall('\n')
data = s.recv(1024)
print data == '111\n'
if data == '111\n':
    print 'send'
    msg = {'msg': 'create_room', 'users': ['1', '2'], 'title': '', 'tag': '', 'type': 'room'}
    s.sendall(json.dumps(msg))
    s.sendall('\n')
    print 'send all'
# s.sendall(pack('>I5s', 5, 'hello'))
# s.sendall('\n')
# s.sendall('Hello, world')# 1）发送数据
data = s.recv(1024)  # 4）接受服务器回显的数据
s.close()
print 'Received', repr(data)  # 打印输出
