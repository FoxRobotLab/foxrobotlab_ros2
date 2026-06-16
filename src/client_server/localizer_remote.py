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

import LocalizerStringConstants as loc_const
from client_server.protocol import recv_result, send_frame

class RemoteLocalizer:
    def __init__(self, robot, server_ip, port, timeout=2.0, gui=None):
        self.robot = robot
        self.gui = gui
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
            self._update_gui(odom, result)
            return result['status'], node_and_pose
        
        except (socket.timeout, ConnectionError, OSError, ValueError) as error:
            print(f'Remote Localization FAILED {error}')
            self.robot.stop()
            return loc_const.temp_lost, None
        

    def close(self):
        self.sock.close()

    def _update_gui(self, odom, result):
        if self.gui is None:
            return

        confidence = result.get('confidence', 0.0)
        self.gui.updateOdomList([odom[0], odom[1], odom[2], confidence])
        self.gui.updateCNode(result['node'])
        fields = {}
        if 'cell' in result:
            fields['current_cell'] = result['cell']
        for key in (
            'localizer_mode',
            'nav_type',
            'mcl',
            'best_pic_scores',
            'best_pic_locs',
            'best_pic_cells',
            'tensorflow_status',
            'tensorflow_version',
            'cnn_device',
            'cnn_model',
            'cnn_model_loaded',
            'cnn_latency_ms',
            'cnn_sequence_length',
            'cnn_sequence_target_length',
            'mcl_variance',
        ):
            if key in result:
                fields[key] = result[key]
        if fields:
            self.gui._send(fields)
        self.gui.updateMatchStatus(result.get('localizer_mode', 'remote localizer'))
