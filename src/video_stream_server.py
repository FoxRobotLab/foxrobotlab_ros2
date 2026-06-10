#!/usr/bin/env python3

import os
import socket
import time

import cv2

from video_protocol import recv_video_frame


HOST = os.environ.get('FOX_VIDEO_SERVER_HOST', '0.0.0.0')
PORT = int(os.environ.get('FOX_VIDEO_SERVER_PORT', '62028'))
SHOW_IMAGES = os.environ.get('FOX_VIDEO_SHOW_IMAGES', '1') == '1'
FPS_REPORT_PERIOD_SECONDS = float(os.environ.get('FOX_VIDEO_FPS_REPORT_PERIOD', '2.0'))


class VideoStreamServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen(1)
        self.latest_frames = {}
        self.frame_count = 0
        self.last_report_time = time.time()

        print(f'Video stream server listening on: {HOST} | {PORT} ...')

    def run_server(self):
        try:
            conn, addr = self.server_socket.accept()
            print(f'Connected to video client: {addr}')

            with conn:
                while True:
                    header, frame = recv_video_frame(conn)
                    stream_name = header['stream']
                    self.latest_frames[stream_name] = frame
                    self.frame_count += 1

                    if SHOW_IMAGES:
                        cv2.imshow(f'Video Stream - {stream_name}', frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break

                    self.report_fps()

        except KeyboardInterrupt:
            pass
        finally:
            self.server_socket.close()
            if SHOW_IMAGES:
                cv2.destroyAllWindows()
            print('Video stream server stopped')

    def report_fps(self):
        now = time.time()
        elapsed = now - self.last_report_time
        if elapsed < FPS_REPORT_PERIOD_SECONDS:
            return

        fps = self.frame_count / elapsed
        print(f'Video receive rate: {fps:.1f} frames/sec')
        self.frame_count = 0
        self.last_report_time = now


if __name__ == '__main__':
    server = VideoStreamServer()
    server.run_server()
