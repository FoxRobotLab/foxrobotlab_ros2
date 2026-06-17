import os
import sys
import math

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
    GUI_PARTICLE_LIMIT = 250

    def __init__(self, olin_map, close_enough):
        self.olin_map = olin_map
        self.close_enough = close_enough
        self.odom_engine = OdomLocalizerEngine(olin_map, close_enough)

    def localize(self, frame_id, frame, odom):
        result = self.odom_engine.localize(frame_id, frame, odom)
        pose = result['pose']
        match_loc = (pose['x'], pose['y'], pose['yaw'])
        cell = result['cell']
        cells = [cell, cell, cell]

        result.update({
            'localizer_mode': 'cnn_mcl_mock',
            'nav_type': 'MCL',
            'mcl': [pose['x'], pose['y'], pose['yaw'], 0.0],
            'mcl_variance': 0.0,
            'mcl_particles': self._mock_particles(match_loc),
            'best_pic_scores': [95.0, 40.0, 15.0],
            'best_pic_locs': [match_loc, match_loc, match_loc],
            'best_pic_cells': cells,
            'tensorflow_status': 'mock',
            'cnn_model': 'mock',
            'cnn_model_loaded': False,
            'cnn_observation_used': False,
            'cnn_observation_rejected': '',
            'correction_source': 'mock_mcl',
            'correction_weight': 0.0,
            'confidence': 95.0,
        })

        return result

    def _mock_particles(self, pose):
        particles = []
        offsets = (-0.45, -0.30, -0.15, 0.0, 0.15, 0.30, 0.45)
        for dx in offsets:
            for dy in offsets:
                if len(particles) >= self.GUI_PARTICLE_LIMIT:
                    return particles
                particles.append([pose[0] + dx, pose[1] + dy, pose[2]])
        return particles


class CnnMclLocalizerEngine:
    MCL_VARIANCE_TRUST = 5.0
    MCL_MAX_CORRECTION_METERS = 2.5
    CNN_MIN_CONFIDENCE = 75.0
    CNN_MIN_MARGIN = 15.0
    CNN_MAX_CORRECTION_METERS = 3.0
    CNN_MAX_BLEND = 0.35
    MCL_MAX_BLEND = 0.65
    GUI_PARTICLE_LIMIT = 500

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
                'mcl_particles': self._particle_locs(),
                'cnn_observation_used': False,
                'cnn_observation_rejected': str(error),
                'correction_source': 'odometry_fallback_after_error',
                'correction_weight': 0.0,
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

        predicted_pose = self._continuous_pose_prediction(odom_pose, move_info)
        nav_type, response_pose, confidence, correction_info = self._select_response(
            predicted_pose,
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
            'odom_pose': list(odom_pose),
            'continuity_pose': list(predicted_pose),
            'correction_source': correction_info['source'],
            'correction_weight': correction_info['weight'],
            'cnn_observation_used': correction_info['cnn_used'],
            'cnn_observation_rejected': correction_info['cnn_rejected'],
            'mcl': [com_pose[0], com_pose[1], com_pose[2], variance],
            'mcl_particles': self._particle_locs(),
            'best_pic_scores': match_scores,
            'best_pic_locs': match_locs,
            'best_pic_cells': prediction['top_cells'],
            'predicted_heading': response_pose[2],
            'heading_source': 'odom_yaw_fallback',
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

    def _continuous_pose_prediction(self, odom_pose, move_info):
        if self.last_known_loc is None:
            return odom_pose
        return (
            self.last_known_loc[0] + move_info[0],
            self.last_known_loc[1] + move_info[1],
            self._normalize_heading(self.last_known_loc[2] + move_info[2]),
        )

    def _select_response(self, predicted_pose, match_locs, match_scores, com_pose, variance):
        correction_info = {
            'source': 'odometry_continuity',
            'weight': 0.0,
            'cnn_used': False,
            'cnn_rejected': '',
        }

        if self._mcl_is_reliable(predicted_pose, com_pose, variance):
            weight = self._mcl_weight(variance)
            corrected = self._blend_pose(predicted_pose, com_pose, weight)
            correction_info.update({'source': 'mcl', 'weight': weight})
            return 'MCL', corrected, 100.0, correction_info

        cnn_ok, reject_reason = self._cnn_is_reliable(predicted_pose, match_locs, match_scores)
        if cnn_ok:
            weight = self._cnn_weight(match_scores)
            corrected = self._blend_pose(predicted_pose, match_locs[0], weight)
            correction_info.update({
                'source': 'cnn_weighted_observation',
                'weight': weight,
                'cnn_used': True,
            })
            return 'CNN_CORRECTION', corrected, match_scores[0], correction_info

        correction_info['cnn_rejected'] = reject_reason
        return 'ODOM', predicted_pose, self.odom_score, correction_info

    def _mcl_is_reliable(self, predicted_pose, com_pose, variance):
        if variance >= self.MCL_VARIANCE_TRUST:
            return False
        return self._distance_2d(predicted_pose, com_pose) <= self.MCL_MAX_CORRECTION_METERS

    def _cnn_is_reliable(self, predicted_pose, match_locs, match_scores):
        if not match_locs or not match_scores:
            return False, 'no_prediction'

        best_score = match_scores[0]
        second_score = match_scores[1] if len(match_scores) > 1 else 0.0
        if best_score < self.CNN_MIN_CONFIDENCE:
            return False, 'low_confidence'
        if best_score - second_score < self.CNN_MIN_MARGIN:
            return False, 'ambiguous_prediction'
        if self._distance_2d(predicted_pose, match_locs[0]) > self.CNN_MAX_CORRECTION_METERS:
            return False, 'too_far_from_odometry'
        return True, ''

    def _mcl_weight(self, variance):
        trust = max(0.0, min(1.0, 1.0 - (variance / self.MCL_VARIANCE_TRUST)))
        return min(self.MCL_MAX_BLEND, 0.25 + 0.40 * trust)

    def _cnn_weight(self, match_scores):
        best_score = match_scores[0]
        second_score = match_scores[1] if len(match_scores) > 1 else 0.0
        confidence = max(0.0, min(1.0, (best_score - self.CNN_MIN_CONFIDENCE) / 25.0))
        margin = max(0.0, min(1.0, (best_score - second_score - self.CNN_MIN_MARGIN) / 35.0))
        return min(self.CNN_MAX_BLEND, 0.10 + 0.25 * min(confidence, margin))

    def _blend_pose(self, base_pose, observation_pose, weight):
        weight = max(0.0, min(1.0, weight))
        return (
            base_pose[0] + (observation_pose[0] - base_pose[0]) * weight,
            base_pose[1] + (observation_pose[1] - base_pose[1]) * weight,
            self._blend_heading(base_pose[2], observation_pose[2], weight),
        )

    def _blend_heading(self, base_heading, observation_heading, weight):
        delta = (observation_heading - base_heading + 180.0) % 360.0 - 180.0
        return self._normalize_heading(base_heading + delta * weight)

    def _normalize_heading(self, heading):
        heading = heading % 360.0
        if heading < 0:
            heading += 360.0
        return heading

    def _distance_2d(self, pose_a, pose_b):
        return math.hypot(pose_a[0] - pose_b[0], pose_a[1] - pose_b[1])

    def _particle_locs(self):
        if self.mcl is None:
            return []
        particles = self.mcl.validPosList[:self.GUI_PARTICLE_LIMIT]
        return [list(particle.getLoc()) for particle in particles]

    def _odom_pose(self, odom):
        return (float(odom['x']), float(odom['y']), float(odom['yaw']))
