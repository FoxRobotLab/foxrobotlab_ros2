import os
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

class OdomLocalizerEngine:
    def __init__(self, olin_map, close_enough):
        self.olin_map = olin_map
        self.close_enough = close_enough

    def localize(self, frame_id, frame, odom):
        pose = (odom['x'], odom['y'], odom['yaw'])

        near_node, node_x, node_y, best_dist = self.olin_map.findClosestNode(pose)
        cell = self.olin_map.convertLocToCell(pose)
        if cell is False:
            cell = near_node
        else:
            cell = int(cell)

        status = loc_const.at_node if best_dist <= self.close_enough else loc_const.close

        return {
            'frame_id': frame_id,
            'status': status,
            'node': near_node,
            'cell': cell,
            'pose': {
                'x': odom['x'],
                'y': odom['y'],
                'yaw': odom['yaw'],
            },
            'confidence': 0.1,
            'localizer_mode': 'odom',
        }


class MockCnnMclLocalizerEngine:
    def __init__(self, olin_map, close_enough):
        self.olin_map = olin_map
        self.close_enough = close_enough
        self.odom_engine = OdomLocalizerEngine(olin_map, close_enough)

    def localize(self, frame_id, frame, odom):
        result = self.odom_engine.localize(frame_id, frame, odom)
        pose = result['pose']
        match_loc = (pose['x'], pose['y'], pose['yaw'])

        result.update({
            'localizer_mode': 'cnn_mcl_mock',
            'nav_type': 'MCL',
            'mcl': [pose['x'], pose['y'], pose['yaw'], 0.0],
            'best_pic_scores': [95.0, 40.0, 15.0],
            'best_pic_locs': [match_loc, match_loc, match_loc],
            'confidence': 95.0,
        })

        return result
