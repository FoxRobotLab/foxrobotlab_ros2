#!/usr/bin/env python3

# Test server for processed TurtleControlProcessor image frames.
# Receives JPEG-encoded images from the client, displays them with OpenCV, and
# sends an acknowledgment after each frame is shown.

import socket
import struct
import select

import cv2
import numpy as np


HOST = '0.0.0.0'
PORT = 62026
HEADER_SIZE = 4


class ImageServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen(1)

        print(f'Server listening on: {HOST} | {PORT} ...')

    def runServer(self):
        try:
            conn, addr = self.server_socket.accept()
            print(f'Connected to client: {addr}')

            with conn:
                while True:
                    # Receive the image size first
                    header = b''
                    while len(header) < HEADER_SIZE:
                        packet = conn.recv(HEADER_SIZE - len(header))
                        if not packet:
                            return
                        header += packet

                    image_size = struct.unpack('!I', header)[0]

                    # Keep reading until the whole image has arrived
                    image_data = b''
                    while len(image_data) < image_size:
                        packet = conn.recv(image_size - len(image_data))
                        if not packet:
                            return
                        image_data += packet

                    # Decode and display the received image
                    image_array = np.frombuffer(image_data, np.uint8)
                    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                    cv2.imshow('Server - Processed Turtle Image', frame)

                    # Let OpenCV update the display window
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

        except KeyboardInterrupt:
            pass
        finally:
            self.server_socket.close()
            cv2.destroyAllWindows()
            print('Server stopped')


if __name__ == '__main__':
    myServ = ImageServer()
    myServ.runServer()
