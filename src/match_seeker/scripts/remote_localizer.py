import socket

import LocalizerStringConstants as loc_const
from localizer_protocol import send_frame, recv_result

class RemoteLocalizer:
    def __init__(self, robot, server_ip, port, timeout=2.0):
        self.robot = robot
        self.frame_id = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((server_ip, port))

    def findLocation(self, cameraImage):
        try:
            odom = self.robot.getOdomData()
            self.frame_id += 1

            send_frame(self.sock, cameraImage, odom, self.frame_id)
            result = recv_result(self.sock)    
            pose = result['pose']
            node_and_pose = (
                result['node'],
                (
                    pose['x'],
                    pose['y'],
                    pose['yaw'],
                )
            )
            return result['status'], node_and_pose
        
        except (socket.timeout, ConnectionError) as error:
            print(f'Remote Localization FAILED {error}')
            self.robot.stop()
            return loc_const.temp_lost, None
        

    def close(self):
        self.sock.close()