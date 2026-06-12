#!/usr/bin/env python3

import os
import socket 
import sys

FOXROBOTLAB_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if FOXROBOTLAB_SRC not in sys.path:
    sys.path.insert(0, FOXROBOTLAB_SRC)

MATCH_SEEKER_SCRIPTS = os.path.join(
    FOXROBOTLAB_SRC,
    'match_seeker',
    'scripts',
)
sys.path.append(os.path.abspath(MATCH_SEEKER_SCRIPTS))

import OlinWorldMap

from client_server.localizer_engines import MockCnnMclLocalizerEngine, OdomLocalizerEngine
from client_server.protocol import recv_frame, send_result

import cv2

HOST = os.environ.get('FOX_LOCALIZER_SERVER_HOST', '0.0.0.0')
PORT = int(os.environ.get('FOX_LOCALIZER_SERVER_PORT', '62027'))
SHOW_IMAGES = os.environ.get('FOX_LOCALIZER_SHOW_IMAGES', '0') == '1'
CLOSE_ENOUGH_METERS = float(os.environ.get('FOX_LOCALIZER_CLOSE_ENOUGH', '0.7'))
LOCALIZER_MODE = os.environ.get('FOX_LOCALIZER_MODE', 'odom')
LOCALIZER_MODEL = os.environ.get('FOX_LOCALIZER_MODEL', 'mock')

class RobotServer():
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen(1)

        self.olinMap = OlinWorldMap.WorldMap()
        if LOCALIZER_MODE == 'cnn_mcl':
            self.localizer = MockCnnMclLocalizerEngine(self.olinMap, CLOSE_ENOUGH_METERS)
        else:
            self.localizer = OdomLocalizerEngine(self.olinMap, CLOSE_ENOUGH_METERS)

        print(f'Server listening on: {HOST} | {PORT} ...')
        print(f'Localizer mode: {LOCALIZER_MODE}, model: {LOCALIZER_MODEL}')

    def run_server(self):
        try:
            conn, addr = self.server_socket.accept()
            print(f'Connected to Client: {addr}')

            with conn:
                while True:
                    header, frame = recv_frame(conn)
                    odom = header['odom']
                    
                    print(f"Frame {header['frame_id']} | Odom {odom}")

                    if SHOW_IMAGES:
                        cv2.imshow('Localizer', frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break

                    result = self.localizer.localize(header['frame_id'], frame, odom)
                    send_result(conn, result)
        finally:
            self.server_socket.close()
            if SHOW_IMAGES:
                cv2.destroyAllWindows()
            print('Server Stopped')

if __name__ == '__main__':
    myServer = RobotServer()
    myServer.run_server()
