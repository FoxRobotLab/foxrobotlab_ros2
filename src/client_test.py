#!/usr/bin/env python3

# Test whether processed OpenCV image data from TurtleControlProcessor can be
# sent to a TCP server, displayed there, and acknowledged.

import socket
import struct
import time

import cv2

from turtle_control_processor import TurtleControlProcessor


SERVER_IP = '10.22.21.57'
PORT = 62026
JPEG_QUALITY = 80
SEND_PERIOD_SECONDS = 0.1


class ImageClient:
    def __init__(self):
        self.processor = TurtleControlProcessor(spin_in_background=True)

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((SERVER_IP, PORT))

        print('Client initiated')
        print(f'Client publishing to: {SERVER_IP} | {PORT} ...')

    def runClient(self):
        try:
            while True:
                # Get the latest processed image from ROS
                image_cv, count = self.processor.getImage()
                if image_cv is None:
                    print('No images')
                    break

                # Encode the OpenCV image as JPEG bytes
                _, encoded_image = cv2.imencode(
                    '.jpg',
                    image_cv,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY],
                )
                image_bytes = encoded_image.tobytes()

                # Send the image size first so the server knows how much data to read
                self.client_socket.sendall(struct.pack('!I', len(image_bytes)))

                # Send the image bytes
                self.client_socket.sendall(image_bytes)

                # Wait for the server to confirm the frame was displayed
                self.client_socket.recv(64)

                # Slow the client down so the server display can keep up
                time.sleep(SEND_PERIOD_SECONDS)

        except KeyboardInterrupt:
            pass
        finally:
            self.client_socket.close()
            self.processor.shutdown()
            print('Client done, disconnecting')


if __name__ == '__main__':
    myClient = ImageClient()
    myClient.runClient()
