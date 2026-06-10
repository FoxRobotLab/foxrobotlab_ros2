#!/usr/bin/env python3

import json
import struct
import time

import cv2
import numpy as np

HEADER_SIZE = 4
QUALITY = 80

def recv_exact(sock, size):
    data = b''

    while len(data) < size:
        packet = sock.recv(size - len(data))

        if not packet:
            print('recv_exact FAILED')
            return None
        
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
    load_json = json.loads(payload_bytes.decode('utf-8'))
    return load_json

def send_frame(sock, image_cv, odom, frame_id):
    success, encoded_image = cv2.imencode(
        '.jpg',
        image_cv,
        [cv2.IMWRITE_JPEG_QUALITY, QUALITY]
    )

    if not success:
        print('image encoding FAILED')
    
    image_bytes = encoded_image.tobytes()

    header = {
        'type': 'frame',
        'frame_id' : frame_id,
        'timestamp' : time.time(),
        'image_size' : len(image_bytes),
        'odom' : {
            'x' : odom[0],
            'y' : odom[1],
            'yaw' : odom[2]
        },
    }

    send_json(sock, header)
    sock.sendall(image_bytes)

def recv_frame(sock):
    header = recv_json(sock)

    if header.get('type') != 'frame' :
        print('receive image FAILED')

    image_size = header['image_size']
    image_bytes = recv_exact(sock, image_size)

    image_array = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if frame is None:
        print('image decoding FAILED')

    return header, frame

def send_result(sock, result):
    result['type'] = 'localization_result'
    send_json(sock, result)

def recv_result(sock):
    result = recv_json(sock)

    if result.get('type') != 'localization_result':
        print(f"Unexpected localization_result : {result.get('type')}")

    return result
