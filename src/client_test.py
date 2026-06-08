#!/usr/bin/env python3

# Test whether processed OpenCV image data from TurtleControlProcessor can be
# sent to a TCP server, displayed there, and acknowledged.

import socket
import struct

import cv2

from turtle_control_processor import TurtleControlProcessor


CLIENT_IP = '141.140.243.85'
PORT = 62026
JPEG_QUALITY = 80
SEND_PERIOD_SECONDS = 0.05


def send_frame(sock, frame):
    _, encoded_image = cv2.imencode(
        '.jpg',
        frame,
        [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY],
    )

    image_bytes = encoded_image.tobytes()
    sock.sendall(struct.pack('!I', len(image_bytes)))
    sock.sendall(image_bytes)


def main():
    processor = TurtleControlProcessor(spin_in_background=True)

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((CLIENT_IP, PORT))
    print(f'Connected to image display server at {CLIENT_IP}:{PORT}')

    try:
        frame, count = processor.getImage()
        send_frame(client_socket, frame)

        response = client_socket.recv(64).decode('utf-8').strip()
        if response:
            print(f'Frame {count}: server replied "{response}"')

    except KeyboardInterrupt:
        pass
    finally:
        client_socket.close()
        processor.shutdown()
        print('Client disconnected.')


if __name__ == '__main__':
    main()
