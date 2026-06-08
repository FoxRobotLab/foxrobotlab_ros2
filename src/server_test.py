#!/usr/bin/env python3

# Test server for processed TurtleControlProcessor image frames.
# Receives JPEG-encoded images from the client, displays them with OpenCV, and
# sends an acknowledgment after each frame is shown.

import socket
import struct

import cv2
import numpy as np


HOST = '0.0.0.0'
PORT = 62026
HEADER_SIZE = 4


def recv_exact(sock, byte_count):
    data = b''
    while len(data) < byte_count:
        packet = sock.recv(byte_count - len(data))
        if not packet:
            return None
        data += packet
    return data


def receive_frame(sock):
    header = recv_exact(sock, HEADER_SIZE)
    if header is None:
        return None

    image_size = struct.unpack('!I', header)[0]
    image_data = recv_exact(sock, image_size)
    if image_data is None:
        return None

    image_array = np.frombuffer(image_data, np.uint8)
    return cv2.imdecode(image_array, cv2.IMREAD_COLOR)


def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)
    print(f'Server listening on {HOST}:{PORT}...')

    try:
        conn, addr = server_socket.accept()
        print(f'Connected to client: {addr}')

        with conn:
            while True:
                frame = receive_frame(conn)
                if frame is None:
                    break

                cv2.imshow('Server - Processed Turtle Image', frame)
                conn.sendall(b'DISPLAYED\n')

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    finally:
        server_socket.close()
        cv2.destroyAllWindows()
        print('Server stopped.')


if __name__ == '__main__':
    main()
