#!/usr/bin/env python3

import os
import socket
import time

from turtle_control_processor import TurtleControlProcessor
from localizer_protocol import send_frame, recv_result

SERVER_IP = os.environ.get('FOX_LOCALIZER_SERVER_IP', '10.22.21.57')
PORT = int(os.environ.get('FOX_LOCALIZER_SERVER_PORT', '62027'))
SEND_PERIOD_SECONDS = float(os.environ.get('FOX_LOCALIZER_SEND_PERIOD', '0.05'))

class RobotClient():
    def __init__(self):
        self.processor = TurtleControlProcessor(spin_in_background=True)

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((SERVER_IP, PORT))

        print('Client initiated')
        print(f'Client publishing to: {SERVER_IP} | {PORT} ...')

    def run_client(self):
        try:
            while True:
                image_cv, count = self.processor.getImage()
                if image_cv is None:
                    print('No images')
                    break

                odom = self.processor.getOdomData()

                send_frame(self.client_socket, image_cv, odom, count)
                result = recv_result(self.client_socket)

                print(f'Localization result: {result}')

                time.sleep(SEND_PERIOD_SECONDS)
        except KeyboardInterrupt:
            pass
        finally:
            self.client_socket.close()
            self.processor.shutdown()
            print('Client Stopping')

if __name__ == '__main__':
    myClient = RobotClient()
    myClient.run_client()
