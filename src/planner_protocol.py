#!/usr/bin/env python3

import json
import struct
import time


HEADER_SIZE = 4


def recv_exact(sock, size):
    data = b''

    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            raise ConnectionError('Socket closed while receiving planner data')
        data += packet

    return data


def send_json(sock, payload):
    data = json.dumps(payload).encode('utf-8')
    sock.sendall(struct.pack('!I', len(data)))
    sock.sendall(data)


def recv_json(sock):
    header = recv_exact(sock, HEADER_SIZE)
    payload_size = struct.unpack('!I', header)[0]
    payload_bytes = recv_exact(sock, payload_size)
    return json.loads(payload_bytes.decode('utf-8'))


def send_status(sock, fields):
    payload = {
        'type': 'planner_status',
        'timestamp': time.time(),
        'fields': fields,
    }
    send_json(sock, payload)


def recv_status(sock):
    payload = recv_json(sock)
    if payload.get('type') != 'planner_status':
        raise ValueError(f"Expected planner_status, got {payload.get('type')}")
    return payload


def send_command(sock, command, fields=None):
    payload = {
        'type': 'planner_command',
        'timestamp': time.time(),
        'command': command,
        'fields': fields or {},
    }
    send_json(sock, payload)


def recv_command(sock):
    payload = recv_json(sock)
    if payload.get('type') != 'planner_command':
        raise ValueError(f"Expected planner_command, got {payload.get('type')}")
    return payload
