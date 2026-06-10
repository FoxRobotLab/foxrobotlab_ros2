#!/usr/bin/env python3

import socket 

from localizer_protocol import recv_frame, send_result
import cv2

HOST = '0.0.0.0'
PORT = 62027

class RobotServer():
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen(1)

        print(f'Server listening on: {HOST} | {PORT} ...')

    def run_server(self):
        try:
            conn, addr = self.server_socket.accept()
            print(f'Connected to Client: {addr}')

            with conn:
                while True:
                    header, frame = recv_frame(conn)
                    odom = header['odom']

                    print(f"Frame {header['frame_id']} | Odom {odom}")

                    cv2.imshow('Localizer', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

                    result = {
                        'frame_id': header['frame_id'],
                        'status': 'close',
                        'node': 1,
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
            cv2.destroyAllWindows()
            print('Server Stopped')

if __name__ == '__main__':
    myServer = RobotServer()
    myServer.run_server()