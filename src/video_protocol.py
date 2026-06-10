#!/usr/bin/env python3

import json
import struct
import time

import cv2
import numpy as np


HEADER_SIZE = 4
DEFAULT_JPEG_QUALITY = 50


def recv_exact(sock, size):
    data = b''

    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            raise ConnectionError('Socket closed while receiving video data')
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


def encode_frame(frame, jpeg_quality=DEFAULT_JPEG_QUALITY, resize_to=None):
    if frame is None:
        raise ValueError('Cannot encode empty video frame')

    if resize_to is not None:
        frame = cv2.resize(frame, resize_to)

    success, encoded_frame = cv2.imencode(
        '.jpg',
        frame,
        [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality],
    )
    if not success:
        raise ValueError('Failed to encode video frame')

    return encoded_frame.tobytes()


def send_video_frame(sock, frame, stream_name, frame_id, jpeg_quality=DEFAULT_JPEG_QUALITY, resize_to=None):
    frame_bytes = encode_frame(frame, jpeg_quality=jpeg_quality, resize_to=resize_to)
    header = {
        'type': 'video_frame',
        'stream': stream_name,
        'frame_id': frame_id,
        'timestamp': time.time(),
        'image_size': len(frame_bytes),
    }

    send_json(sock, header)
    sock.sendall(frame_bytes)


def recv_video_frame(sock):
    header = recv_json(sock)

    if header.get('type') != 'video_frame':
        raise ValueError(f"Expected video_frame, got {header.get('type')}")

    frame_bytes = recv_exact(sock, header['image_size'])
    image_array = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if frame is None:
        raise ValueError('Failed to decode video frame')

    return header, frame
