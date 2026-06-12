#!/usr/bin/env python3

import os
import socket
import sys
import time

import cv2

FOXROBOTLAB_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if FOXROBOTLAB_SRC not in sys.path:
    sys.path.insert(0, FOXROBOTLAB_SRC)

from turtle_control_processor import TurtleControlProcessor
from client_server.protocol import send_video_frame


SERVER_IP = os.environ.get('FOX_VIDEO_SERVER_IP', '10.22.21.57')
PORT = int(os.environ.get('FOX_VIDEO_SERVER_PORT', '62028'))
TARGET_FPS = float(os.environ.get('FOX_VIDEO_TARGET_FPS', '30.0'))
SEND_PERIOD_SECONDS = 1.0 / TARGET_FPS
JPEG_QUALITY = int(os.environ.get('FOX_VIDEO_JPEG_QUALITY', '45'))
RESIZE_TO = (
    int(os.environ.get('FOX_VIDEO_RESIZE_WIDTH', '320')),
    int(os.environ.get('FOX_VIDEO_RESIZE_HEIGHT', '240')),
)
SEND_DEPTH = os.environ.get('FOX_VIDEO_SEND_DEPTH', '1') == '1'


class VideoStreamClient:
    def __init__(self):
        self.processor = TurtleControlProcessor(spin_in_background=True)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((SERVER_IP, PORT))
        self.frame_id = 0

        print('Video stream client initiated')
        print(f'Video streaming to: {SERVER_IP} | {PORT} ...')

    def run_client(self):
        try:
            while True:
                loop_start = time.time()
                image_cv, count = self.processor.getImage()
                if image_cv is None:
                    print('No camera images')
                    break

                self.frame_id = count
                send_video_frame(
                    self.client_socket,
                    image_cv,
                    'camera',
                    self.frame_id,
                    jpeg_quality=JPEG_QUALITY,
                    resize_to=RESIZE_TO,
                )

                if SEND_DEPTH:
                    depth_cv = self.processor.getDepth()
                    depth_cv = depth_cv.astype('uint8')
                    depth_display = cv2.normalize(depth_cv, None, 0, 255, cv2.NORM_MINMAX)
                    send_video_frame(
                        self.client_socket,
                        depth_display,
                        'depth',
                        self.frame_id,
                        jpeg_quality=JPEG_QUALITY,
                        resize_to=RESIZE_TO,
                    )

                elapsed = time.time() - loop_start
                sleep_time = SEND_PERIOD_SECONDS - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            pass
        finally:
            self.client_socket.close()
            self.processor.shutdown()
            print('Video stream client stopped')


if __name__ == '__main__':
    client = VideoStreamClient()
    client.run_client()
