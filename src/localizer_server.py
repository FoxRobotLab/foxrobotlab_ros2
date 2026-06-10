#!/usr/bin/env python3

import os
import socket 
import sys

MATCH_SEEKER_SCRIPTS = os.path.join(
    os.path.dirname(__file__),
    'match_seeker',
    'scripts',
)
sys.path.append(os.path.abspath(MATCH_SEEKER_SCRIPTS))

import OlinWorldMap

import LocalizerStringConstants as loc_const
from localizer_protocol import recv_frame, send_result

import cv2

HOST = os.environ.get('FOX_LOCALIZER_SERVER_HOST', '0.0.0.0')
PORT = int(os.environ.get('FOX_LOCALIZER_SERVER_PORT', '62027'))
SHOW_IMAGES = os.environ.get('FOX_LOCALIZER_SHOW_IMAGES', '0') == '1'
CLOSE_ENOUGH_METERS = float(os.environ.get('FOX_LOCALIZER_CLOSE_ENOUGH', '0.7'))

class RobotServer():
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen(1)

        self.olinMap = OlinWorldMap.WorldMap()

        print(f'Server listening on: {HOST} | {PORT} ...')

    def run_server(self):
        try:
            conn, addr = self.server_socket.accept()
            print(f'Connected to Client: {addr}')

            with conn:
                while True:
                    header, frame = recv_frame(conn)
                    odom = header['odom']

                    pose = (odom['x'], odom['y'], odom['yaw'])
                    near_node, node_x, node_y, best_dist = self.olinMap.findClosestNode(pose)
                    cell = self.olinMap.convertLocToCell(pose)
                    if cell is False:
                        cell = near_node
                    else:
                        cell = int(cell)
                    status = loc_const.at_node if best_dist <= CLOSE_ENOUGH_METERS else loc_const.close
                    
                    print(f"Frame {header['frame_id']} | Odom {odom}")

                    if SHOW_IMAGES:
                        cv2.imshow('Localizer', frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break

                    result = {
                        'frame_id': header['frame_id'],
                        'status': status,
                        'node': near_node,
                        'cell': cell,
                        'pose': {
                            'x': odom['x'],
                            'y': odom['y'],
                            'yaw': odom['yaw'],
                        },
                        'confidence': 0.1,
                    }

                    send_result(conn, result)
        finally:
            self.server_socket.close()
            if SHOW_IMAGES:
                cv2.destroyAllWindows()
            print('Server Stopped')

if __name__ == '__main__':
    myServer = RobotServer()
    myServer.run_server()
