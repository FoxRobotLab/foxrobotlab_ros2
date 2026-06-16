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
import MonteCarloLocalize

from client_server.cnn_model_adapter import CnnModelAdapter

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


class CnnMclLocalizerEngine:
    def __init__(
        self,
        olin_map,
        close_enough,
        model_path,
        show_mcl=False,
        particle_count=250,
    ):
        self.olin_map = olin_map
        self.close_enough = close_enough
        self.odom_engine = OdomLocalizerEngine(olin_map, close_enough)
        self.cnn = CnnModelAdapter(model_path)
        self.show_mcl = show_mcl
        self.particle_count = int(particle_count)
        self.mcl = None
        self.previous_odom_pose = None
        self.odom_score = 100.0
        self.last_known_loc = None

    def localize(self, frame_id, frame, odom):
        odom_pose = self._odom_pose(odom)
        try:
            return self._localize_cnn_mcl(frame_id, frame, odom_pose)
        except Exception as error:
            result = self.odom_engine.localize(frame_id, frame, odom)
            result.update({
                'localizer_mode': 'cnn_mcl_error',
                'nav_type': 'ODOM',
                'tensorflow_status': f'error: {error}',
                'cnn_model_loaded': self.cnn.model_loaded,
                'cnn_model': self.cnn.model_path,
            })
            return result

    def _localize_cnn_mcl(self, frame_id, frame, odom_pose):
        self._ensure_mcl(odom_pose)
        move_info = self._move_info(odom_pose)
        prediction = self.cnn.predict(frame)
        match_locs = self._prediction_locs(prediction['top_cells'], odom_pose[2])
        match_scores = prediction['top_scores']

        mcl_data = {
            'matchPoses': match_locs,
            'matchScores': match_scores,
            'odomPose': odom_pose,
            'odomScore': self.odom_score,
        }
        com_pose, variance = self.mcl.mclCycle(
            mcl_data,
            move_info,
            show_map=self.show_mcl,
        )
        self.previous_odom_pose = odom_pose
        self.odom_score = max(0.01, self.odom_score - 0.1)

        nav_type, response_pose, confidence = self._select_response(
            odom_pose,
            match_locs,
            match_scores,
            com_pose,
            variance,
        )
        node, node_x, node_y, best_dist = self.olin_map.findClosestNode(response_pose)
        cell = self.olin_map.convertLocToCell(response_pose)
        if cell is False:
            cell = node
        else:
            cell = int(cell)

        status = loc_const.at_node if best_dist <= self.close_enough else loc_const.close
        self.last_known_loc = response_pose

        return {
            'frame_id': frame_id,
            'status': status,
            'node': node,
            'cell': cell,
            'pose': {
                'x': response_pose[0],
                'y': response_pose[1],
                'yaw': response_pose[2],
            },
            'confidence': confidence,
            'localizer_mode': 'cnn_mcl',
            'nav_type': nav_type,
            'mcl': [com_pose[0], com_pose[1], com_pose[2], variance],
            'best_pic_scores': match_scores,
            'best_pic_locs': match_locs,
            'best_pic_cells': prediction['top_cells'],
            'tensorflow_status': 'ok',
            'tensorflow_version': prediction['tensorflow_version'],
            'gpu_devices': prediction['gpu_devices'],
            'logical_gpu_devices': prediction['logical_gpu_devices'],
            'cnn_device': prediction['device'],
            'cnn_model': prediction['model_path'],
            'cnn_model_loaded': prediction['model_loaded'],
            'cnn_latency_ms': prediction['latency_ms'],
            'cnn_sequence_length': prediction['sequence_length'],
            'cnn_sequence_target_length': prediction['sequence_target_length'],
            'mcl_variance': variance,
        }

    def _ensure_mcl(self, odom_pose):
        if self.mcl is not None:
            return
        self.mcl = MonteCarloLocalize.monteCarloLoc(self.olin_map)
        self.mcl.initializeParticles(self.particle_count, point=odom_pose)
        self.previous_odom_pose = odom_pose

    def _move_info(self, odom_pose):
        if self.previous_odom_pose is None:
            return (0.0, 0.0, 0.0)
        return (
            odom_pose[0] - self.previous_odom_pose[0],
            odom_pose[1] - self.previous_odom_pose[1],
            odom_pose[2] - self.previous_odom_pose[2],
        )

    def _prediction_locs(self, cells, yaw):
        locs = []
        for cell in cells:
            xy = self.olin_map.getLocation(int(cell))
            if xy is not None:
                locs.append((xy[0], xy[1], yaw))
        while len(locs) < 3:
            locs.append((0.0, 0.0, yaw))
        return locs

    def _select_response(self, odom_pose, match_locs, match_scores, com_pose, variance):
        if variance < 5.0:
            return 'MCL', com_pose, 100.0
        if match_scores and match_scores[0] >= 5.0:
            return 'CNN', match_locs[0], match_scores[0]
        return 'ODOM', odom_pose, self.odom_score

    def _odom_pose(self, odom):
        return (float(odom['x']), float(odom['y']), float(odom['yaw']))
