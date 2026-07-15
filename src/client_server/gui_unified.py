#!/usr/bin/env python3

import os
import socket
import sys
import threading
import time

import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

FOXROBOTLAB_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if FOXROBOTLAB_SRC not in sys.path:
    sys.path.insert(0, FOXROBOTLAB_SRC)

MATCH_SEEKER_SCRIPTS = os.path.join(FOXROBOTLAB_SRC, 'match_seeker', 'scripts')
if MATCH_SEEKER_SCRIPTS not in sys.path:
    sys.path.append(os.path.abspath(MATCH_SEEKER_SCRIPTS))

import OlinWorldMap

from client_server.protocol import recv_status, recv_video_frame, send_command


VIDEO_HOST = os.environ.get('FOX_VIDEO_SERVER_HOST', '0.0.0.0')
VIDEO_PORT = int(os.environ.get('FOX_VIDEO_SERVER_PORT', '62028'))
PLANNER_STATUS_HOST = os.environ.get('FOX_GUI_STATUS_SERVER_HOST', '0.0.0.0')
PLANNER_STATUS_PORT = int(os.environ.get('FOX_GUI_STATUS_SERVER_PORT', '62029'))
PLANNER_COMMAND_IP = os.environ.get('FOX_GUI_COMMAND_SERVER_IP', '10.22.21.57')
PLANNER_COMMAND_PORT = int(os.environ.get('FOX_GUI_COMMAND_SERVER_PORT', '62030'))
FPS_REPORT_PERIOD_SECONDS = float(os.environ.get('FOX_VIDEO_FPS_REPORT_PERIOD', '2.0'))
GUI_REFRESH_MS = int(os.environ.get('FOX_GUI_REFRESH_MS', '33'))


class VideoReceiver(QtCore.QThread):
    status_changed = QtCore.pyqtSignal(str)
    fps_changed = QtCore.pyqtSignal(str)
    log_message = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._server_socket = None
        self._client_socket = None
        self._frame_count = 0
        self._last_report_time = time.time()
        self._latest_frames = {}
        self._latest_frames_lock = threading.Lock()

    def run(self):
        while self._running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                    self._server_socket = server_socket
                    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    server_socket.bind((VIDEO_HOST, VIDEO_PORT))
                    server_socket.listen(1)
                    server_socket.settimeout(0.5)
                    self.status_changed.emit(f'Video: listening {VIDEO_HOST}:{VIDEO_PORT}')

                    while self._running:
                        try:
                            conn, addr = server_socket.accept()
                            break
                        except socket.timeout:
                            continue
                    else:
                        continue

                    self.status_changed.emit(f'Video: connected {addr[0]}')
                    with conn:
                        self._client_socket = conn
                        conn.settimeout(0.5)
                        while self._running:
                            try:
                                header, frame = recv_video_frame(conn)
                            except socket.timeout:
                                continue
                            stream_name = header['stream']
                            self._store_latest_frame(stream_name, frame)
                            self._report_fps()

            except (ConnectionError, OSError, ValueError) as error:
                if self._running:
                    self.status_changed.emit('Video: reconnecting')
                    self.log_message.emit(f'Video receiver: {error}')
                    self.msleep(1000)
            finally:
                self._client_socket = None
                self._server_socket = None

    def stop(self):
        self._running = False
        for sock in (self._client_socket, self._server_socket):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    def take_latest_frames(self):
        with self._latest_frames_lock:
            frames = self._latest_frames
            self._latest_frames = {}
        return frames

    def _store_latest_frame(self, stream_name, frame):
        with self._latest_frames_lock:
            self._latest_frames[stream_name] = frame

    def _report_fps(self):
        self._frame_count += 1
        now = time.time()
        elapsed = now - self._last_report_time
        if elapsed < FPS_REPORT_PERIOD_SECONDS:
            return

        fps = self._frame_count / elapsed
        self.fps_changed.emit(f'{fps:.1f} fps')
        self._frame_count = 0
        self._last_report_time = now


class PlannerStatusReceiver(QtCore.QThread):
    status_received = QtCore.pyqtSignal(dict)
    log_message = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._server_socket = None
        self._client_socket = None

    def run(self):
        while self._running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                    self._server_socket = server_socket
                    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    server_socket.bind((PLANNER_STATUS_HOST, PLANNER_STATUS_PORT))
                    server_socket.listen(1)
                    server_socket.settimeout(0.5)
                    self.log_message.emit(
                        f'Planner status listening {PLANNER_STATUS_HOST}:{PLANNER_STATUS_PORT}'
                    )

                    while self._running:
                        try:
                            conn, addr = server_socket.accept()
                            break
                        except socket.timeout:
                            continue
                    else:
                        continue

                    self.log_message.emit(f'Planner status connected {addr[0]}')
                    with conn:
                        self._client_socket = conn
                        conn.settimeout(0.5)
                        while self._running:
                            try:
                                payload = recv_status(conn)
                            except socket.timeout:
                                continue
                            self.status_received.emit(payload['fields'])

            except (ConnectionError, OSError, ValueError) as error:
                if self._running:
                    self.log_message.emit(f'Planner status receiver: {error}')
                    self.msleep(1000)
            finally:
                self._client_socket = None
                self._server_socket = None

    def stop(self):
        self._running = False
        for sock in (self._client_socket, self._server_socket):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass


class ImagePanel(QtWidgets.QFrame):
    def __init__(self, title, placeholder, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._overlay_text = ''
        self.setObjectName('imagePanel')
        self.setMinimumSize(260, 220)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setObjectName('panelTitle')
        self.image_label = QtWidgets.QLabel(placeholder)
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(180, 160)
        self.image_label.setScaledContents(False)
        self.image_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.image_label, 1)

    def set_frame(self, frame):
        self._pixmap = frame_to_pixmap(frame)
        self._update_scaled_pixmap()

    def set_overlay_text(self, text):
        self._overlay_text = str(text or '')
        self._update_scaled_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        if self._pixmap is None:
            return

        scaled = self._pixmap.scaled(
            self.image_label.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        if self._overlay_text:
            scaled = QtGui.QPixmap(scaled)
            painter = QtGui.QPainter(scaled)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            font = painter.font()
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)

            metrics = QtGui.QFontMetrics(font)
            text_width = metrics.horizontalAdvance(self._overlay_text)
            rect = QtCore.QRect(10, 10, text_width + 20, metrics.height() + 12)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(20, 24, 22, 210))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(QtGui.QColor(255, 255, 255))
            painter.drawText(rect, QtCore.Qt.AlignCenter, self._overlay_text)
            painter.end()
        self.image_label.setPixmap(scaled)


class FieldPanel(QtWidgets.QGroupBox):
    def __init__(self, title, rows, parent=None):
        super().__init__(title, parent)
        self.value_labels = {}

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(12, 18, 12, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(7)

        for row, (key, label, initial) in enumerate(rows):
            name_label = QtWidgets.QLabel(label)
            name_label.setObjectName('fieldName')
            value_label = QtWidgets.QLabel(initial)
            value_label.setObjectName('fieldValue')
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            layout.addWidget(name_label, row, 0, QtCore.Qt.AlignTop)
            layout.addWidget(value_label, row, 1)
            self.value_labels[key] = value_label

        layout.setColumnStretch(1, 1)

    def set_value(self, key, value):
        if key in self.value_labels:
            self.value_labels[key].setText(str(value))


class LocalizationComparisonTable(QtWidgets.QGroupBox):
    ROW_KEYS = ('odom', 'mcl', 'cnn_selected', 'cnn_1', 'cnn_2', 'cnn_3')
    COLUMNS = ('Source', 'x', 'y', 'yaw', 'conf')

    def __init__(self, parent=None):
        super().__init__('Localization Comparison', parent)
        self.setObjectName('comparisonPanel')
        self.setMinimumWidth(430)
        self.table = QtWidgets.QTableWidget(len(self.ROW_KEYS), len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(QtCore.Qt.NoFocus)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(40)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setMinimumHeight(230)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 18, 10, 10)
        layout.addWidget(self.table)
        self.clear()

    def clear(self):
        for row, key in enumerate(self.ROW_KEYS):
            self._set_row(row, self._default_label(key), None, None)

    def update_from_fields(self, fields):
        if 'odom' in fields:
            self._set_row(0, 'Odom', fields.get('odom'), fields.get('confidence'))
        if 'mcl' in fields:
            self._set_row(1, 'MCL', fields.get('mcl'), self._mcl_confidence(fields))

        best_locs = fields.get('best_pic_locs')
        best_scores = fields.get('best_pic_scores')
        best_cells = fields.get('best_pic_cells')
        if isinstance(best_locs, (list, tuple)) or isinstance(best_scores, (list, tuple)) or isinstance(best_cells, (list, tuple)):
            self._set_cnn_rows(best_locs, best_scores, best_cells)

    def _set_cnn_rows(self, locs, scores, cells):
        selected_loc = self._list_item(locs, 0)
        selected_score = self._list_item(scores, 0)
        selected_cell = self._list_item(cells, 0)
        selected_label = 'CNN sel'
        if selected_cell not in (None, ''):
            selected_label = f'{selected_label} ({selected_cell})'
        self._set_row(2, selected_label, selected_loc, selected_score)

        for index in range(3):
            loc = self._list_item(locs, index)
            score = self._list_item(scores, index)
            cell = self._list_item(cells, index)
            label = f'CNN #{index + 1}'
            if cell not in (None, ''):
                label = f'{label} ({cell})'
            self._set_row(3 + index, label, loc, score)

    def _set_row(self, row, label, pose, confidence):
        values = self._pose_values(pose)
        row_values = [
            label,
            values[0],
            values[1],
            values[2],
            self._format_value(confidence),
        ]
        for col, value in enumerate(row_values):
            item = QtWidgets.QTableWidgetItem(value)
            if col > 0:
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row, col, item)

    def _pose_values(self, pose):
        coerced = self._coerce_pose(pose)
        if coerced is None:
            return ('unknown', 'unknown', 'unknown')
        return tuple(self._format_value(value) for value in coerced)

    def _coerce_pose(self, value):
        if isinstance(value, dict):
            value = (value.get('x'), value.get('y'), value.get('yaw'))
        if not isinstance(value, (list, tuple)) or len(value) < 3:
            return None
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except (TypeError, ValueError):
            return None

    def _format_value(self, value):
        if value is None:
            return 'unknown'
        try:
            return f'{float(value):.2f}'
        except (TypeError, ValueError):
            return str(value)

    def _mcl_confidence(self, fields):
        nav_type = str(fields.get('nav_type', '')).upper()
        if nav_type == 'MCL':
            return fields.get('confidence')
        return fields.get('mcl_variance')

    def _default_label(self, key):
        return {
            'odom': 'Odom',
            'mcl': 'MCL',
            'cnn_selected': 'CNN sel',
            'cnn_1': 'CNN #1',
            'cnn_2': 'CNN #2',
            'cnn_3': 'CNN #3',
        }[key]

    def _list_item(self, value, index):
        if isinstance(value, (list, tuple)) and len(value) > index:
            return value[index]
        return None


class MclVisualization(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super().__init__('', parent)
        self.setObjectName('mclPanel')
        self.olin_map = OlinWorldMap.WorldMap()
        self.pose_history = []
        self.mcl_particles = []
        self.max_history = 120
        self._pixmap = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 12)
        layout.setSpacing(8)

        title = QtWidgets.QLabel('MCL Localization Window')
        title.setObjectName('mclTitle')
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)

        self.map_label = QtWidgets.QLabel('Waiting for localization data')
        self.map_label.setObjectName('mapCanvas')
        self.map_label.setAlignment(QtCore.Qt.AlignCenter)
        self.map_label.setMinimumSize(520, 330)
        self.map_label.setScaledContents(False)
        layout.addWidget(self.map_label, 1)
        self.update_map()

    def update_pose(self, pose, odom_pose=None, cnn_locs=None, mcl_pose=None, mcl_particles=None):
        pose_tuple = self._coerce_pose(pose)
        if pose_tuple is not None:
            self.pose_history.append(pose_tuple)
            self.pose_history = self.pose_history[-self.max_history:]

        if mcl_particles is not None:
            self.mcl_particles = self._coerce_pose_list(mcl_particles)

        self.update_map(
            odom_pose=self._coerce_pose(odom_pose),
            cnn_locs=self._coerce_pose_list(cnn_locs),
            mcl_pose=self._coerce_pose(mcl_pose),
        )

    def update_map(self, odom_pose=None, cnn_locs=None, mcl_pose=None):
        self.olin_map.cleanMapImage(obstacles=True, cells=True, drawCellNum=False)

        for particle in self.mcl_particles:
            self.olin_map.drawPose(particle, size=1, color=(75, 75, 75), fill=True)

        for index, pose in enumerate(self.pose_history):
            age = index / max(1, len(self.pose_history) - 1)
            trail_value = int(150 - 90 * age)
            color = (trail_value, trail_value, trail_value)
            self.olin_map.drawPose(pose, size=2, color=color, fill=True)

        if cnn_locs:
            for loc in cnn_locs[:3]:
                self.olin_map.drawPose(loc, size=3, color=(255, 0, 255), fill=False)

        if odom_pose is not None:
            self.olin_map.drawPose(odom_pose, size=4, color=(0, 170, 255), fill=False)

        if mcl_pose is not None:
            self.olin_map.drawPose(mcl_pose, size=5, color=(0, 200, 0), fill=False)

        if self.pose_history:
            current_pose = self.pose_history[-1]
            self.olin_map.drawPose(current_pose, size=9, color=(0, 0, 0), fill=False)
            self.olin_map.drawPose(current_pose, size=7, color=(0, 0, 255), fill=True)

        self._pixmap = frame_to_pixmap(self.olin_map.currentMapImg)
        self._update_scaled_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        if self._pixmap is None:
            return

        scaled = self._pixmap.scaled(
            self.map_label.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self.map_label.clear()
        self.map_label.setText('')
        self.map_label.setPixmap(scaled)

    def _coerce_pose(self, value):
        if isinstance(value, dict):
            value = (value.get('x'), value.get('y'), value.get('yaw'))
        if not isinstance(value, (list, tuple)) or len(value) < 3:
            return None
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except (TypeError, ValueError):
            return None

    def _coerce_pose_list(self, value):
        if not isinstance(value, (list, tuple)):
            return []
        poses = []
        for item in value:
            pose = self._coerce_pose(item)
            if pose is not None:
                poses.append(pose)
        return poses


class UnifiedSeekerGUI(QtWidgets.QMainWindow):
    def __init__(self, start_threads=True):
        super().__init__()
        self.command_sock = None
        self.video_thread = None
        self.status_thread = None
        self.latest_fields = {}
        self._last_log_signatures = {}
        self._last_odom_log_time = 0.0
        self.video_refresh_timer = QtCore.QTimer(self)
        self.video_refresh_timer.timeout.connect(self._display_latest_frames)

        self.setWindowTitle('Seeker')
        self.resize(1580, 930)
        self.setMinimumSize(1180, 760)
        self._build_layout()
        self._append_log('Unified PyQt GUI ready')

        if start_threads:
            self._start_workers()

    def _build_layout(self):
        self._install_style()

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QGridLayout(central)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self._build_top_bar(layout)
        self._build_main_area(layout)
        self._build_log(layout)

        layout.setRowStretch(0, 0)
        layout.setRowStretch(1, 7)
        layout.setRowStretch(2, 2)
        layout.setColumnStretch(0, 1)

    def _build_top_bar(self, layout):
        top_bar = QtWidgets.QFrame()
        top_bar.setObjectName('topBar')
        top_layout = QtWidgets.QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 8, 12, 8)
        top_layout.setSpacing(18)

        self.video_status_label = QtWidgets.QLabel(f'Video: listening {VIDEO_HOST}:{VIDEO_PORT}')
        self.command_status_label = QtWidgets.QLabel('Commands: idle')
        self.fps_label = QtWidgets.QLabel('0.0 fps')
        self.battery_label = QtWidgets.QLabel('Battery: unknown')
        self.quit_button = QtWidgets.QPushButton('Quit')
        self.quit_button.clicked.connect(self.close)

        for label in (
            self.video_status_label,
            self.command_status_label,
            self.fps_label,
            self.battery_label,
        ):
            label.setObjectName('topValue')
            top_layout.addWidget(label)

        top_layout.addStretch(1)
        top_layout.addWidget(self.quit_button)
        layout.addWidget(top_bar, 0, 0)

    def _build_main_area(self, layout):
        main_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_split.setChildrenCollapsible(False)
        left_widget = self._build_left_area()
        right_widget = self._build_map_area()

        main_split.addWidget(left_widget)
        main_split.addWidget(right_widget)
        main_split.setStretchFactor(0, 6)
        main_split.setStretchFactor(1, 5)
        layout.addWidget(main_split, 1, 0)

    def _build_left_area(self):
        widget = QtWidgets.QWidget()
        widget.setMinimumWidth(620)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.depth_panel = ImagePanel('Depth', 'Waiting for depth stream')
        self.camera_panel = ImagePanel('Camera', 'Waiting for camera stream')
        self.robot_panel = FieldPanel('Robot Status', self._robot_status_rows())
        self.robot_panel.setMaximumWidth(340)
        self.localization_table = LocalizationComparisonTable()

        sensor_row = QtWidgets.QHBoxLayout()
        sensor_row.setSpacing(12)
        sensor_row.addWidget(self.depth_panel, 1)
        sensor_row.addWidget(self.camera_panel, 1)

        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(12)
        status_row.addWidget(self.robot_panel, 2)
        status_row.addWidget(self.localization_table, 3)

        layout.addLayout(sensor_row, 3)
        layout.addLayout(status_row, 2)
        return widget

    def _build_map_area(self):
        widget = QtWidgets.QWidget()
        widget.setMinimumWidth(520)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.mcl_panel = MclVisualization()
        self.controls_panel = self._build_controls_panel()
        layout.addWidget(self.mcl_panel, 1)
        layout.addWidget(self.controls_panel, 0)
        return widget

    def _robot_status_rows(self):
        return [
            ('current_cell', 'Current cell', 'unknown'),
            ('next_cell', 'Next cell', 'unknown'),
            ('target_distance', 'Target distance', 'unknown'),
            ('current_yaw', 'Current yaw', 'unknown'),
            ('turn_state', 'Turn state', 'unknown'),
            ('nav_state', 'Navigation brain/state', 'unknown'),
            ('cnn_model', 'CNN model', 'unknown'),
        ]

    def _build_controls_panel(self):
        panel = QtWidgets.QGroupBox('Navigation Controls')
        layout = QtWidgets.QGridLayout(panel)
        layout.setContentsMargins(12, 18, 12, 12)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        self.start_entry = QtWidgets.QLineEdit()
        self.yaw_entry = QtWidgets.QLineEdit()
        self.dest_entry = QtWidgets.QLineEdit()
        self.start_entry.setPlaceholderText('start/current cell')
        self.yaw_entry.setPlaceholderText('yaw')
        self.dest_entry.setPlaceholderText('destination')

        layout.addWidget(QtWidgets.QLabel('Start/current cell'), 0, 0)
        layout.addWidget(self.start_entry, 0, 1)
        layout.addWidget(QtWidgets.QLabel('Yaw'), 1, 0)
        layout.addWidget(self.yaw_entry, 1, 1)
        layout.addWidget(QtWidgets.QLabel('Destination'), 2, 0)
        layout.addWidget(self.dest_entry, 2, 1)

        buttons = [
            ('Set Start', self._send_start),
            ('Set Goal', self._send_goal),
            ('Pause', lambda: self._send_command('pause_motors')),
            ('Run Motors', lambda: self._send_command('run_motors')),
            ('Quit Robot', lambda: self._send_command('quit')),
        ]
        for index, (label, callback) in enumerate(buttons):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            layout.addWidget(button, 0 + index // 3, 2 + index % 3)

        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 1)
        layout.setColumnStretch(4, 1)
        return panel

    def _build_log(self, layout):
        log_panel = QtWidgets.QGroupBox('Log')
        log_layout = QtWidgets.QVBoxLayout(log_panel)
        log_layout.setContentsMargins(10, 16, 10, 10)
        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(300)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_panel, 2, 0)

    def _install_style(self):
        self.setStyleSheet(
            '''
            QMainWindow {
                background: #f1f2ee;
            }
            QFrame#topBar {
                background: #dfe2dd;
                border: 1px solid #a3a7a1;
            }
            QLabel#topValue {
                font-weight: 600;
                color: #1f2420;
            }
            QFrame#imagePanel,
            QGroupBox {
                background: #dcdfd9;
                border: 1px solid #7e857e;
                border-radius: 3px;
            }
            QGroupBox {
                margin-top: 12px;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel#panelTitle {
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#fieldName {
                color: #3c433e;
                font-weight: 600;
            }
            QLabel#fieldValue {
                color: #111612;
            }
            QGroupBox#mclPanel {
                background: #4b514d;
                border: 1px solid #252a27;
                color: #f6f8f3;
            }
            QGroupBox#mclPanel::title {
                color: #f6f8f3;
            }
            QGroupBox#mclPanel QLabel#fieldName,
            QGroupBox#mclPanel QLabel#fieldValue,
            QGroupBox#mclPanel QLabel#mclTitle {
                color: #f6f8f3;
            }
            QLabel#mclTitle {
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#mapCanvas {
                background: #f8f9f6;
                border: 2px solid #262b28;
            }
            QLineEdit {
                background: #ffffff;
                border: 1px solid #a3a7a1;
                border-radius: 2px;
                padding: 5px 7px;
            }
            QPushButton {
                background: #edf0eb;
                border: 1px solid #8d928b;
                border-radius: 3px;
                padding: 7px 10px;
                min-height: 26px;
            }
            QPushButton:hover {
                background: #f7f8f5;
            }
            QPushButton:pressed {
                background: #d3d8d0;
            }
            QPlainTextEdit {
                background: #f8f9f6;
                border: 1px solid #a3a7a1;
                font-family: monospace;
                font-size: 12px;
            }
            QTableWidget {
                background: #f8f9f6;
                alternate-background-color: #eef1eb;
                border: 1px solid #a3a7a1;
                gridline-color: #b9bdb5;
                font-size: 12px;
            }
            QHeaderView::section {
                background: #d4d8d1;
                border: 1px solid #a3a7a1;
                padding: 4px;
                font-weight: 700;
            }
            '''
        )

    def _start_workers(self):
        self.video_thread = VideoReceiver(self)
        self.video_thread.status_changed.connect(self.video_status_label.setText)
        self.video_thread.fps_changed.connect(self.fps_label.setText)
        self.video_thread.log_message.connect(self._append_log)
        self.video_thread.start()
        self.video_refresh_timer.start(GUI_REFRESH_MS)

        self.status_thread = PlannerStatusReceiver(self)
        self.status_thread.status_received.connect(self._apply_planner_status)
        self.status_thread.log_message.connect(self._append_log)
        self.status_thread.start()

    def _display_latest_frames(self):
        if self.video_thread is None:
            return

        for stream_name, frame in self.video_thread.take_latest_frames().items():
            self._set_frame(stream_name, frame)

    def _set_frame(self, stream_name, frame):
        if stream_name == 'camera':
            self.camera_panel.set_frame(frame)
            self.camera_panel.set_overlay_text(self._camera_overlay_text())
        elif stream_name == 'depth':
            self.depth_panel.set_frame(frame)

    def _apply_planner_status(self, fields):
        self.latest_fields.update(fields)
        self._apply_top_status(fields)
        self._apply_robot_status(fields)
        self._apply_camera_overlay()
        self._apply_localization_table()
        self._apply_map_status(fields)
        self._log_status_updates(fields)

        if 'log' in fields:
            self._append_log(fields['log'])

    def _apply_top_status(self, fields):
        if 'battery' in fields:
            self.battery_label.setText(f"Battery: {fields['battery']}")

    def _apply_robot_status(self, fields):
        if 'current_cell' in fields:
            self.robot_panel.set_value('current_cell', fields['current_cell'])
        if 'next_node' in fields:
            self.robot_panel.set_value('next_cell', fields['next_node'])
        if 'target_distance' in fields:
            self.robot_panel.set_value('target_distance', self._format_float(fields['target_distance'], 2))
        if 'turn_state' in fields:
            self.robot_panel.set_value('turn_state', fields['turn_state'])
        if 'cnn_model' in fields:
            self.robot_panel.set_value('cnn_model', os.path.basename(str(fields['cnn_model'])))

        self.robot_panel.set_value('nav_state', self._nav_state_text())
        self.robot_panel.set_value('current_yaw', self._current_yaw_text())

    def _apply_camera_overlay(self):
        self.camera_panel.set_overlay_text(self._camera_overlay_text())

    def _apply_localization_table(self):
        self.localization_table.update_from_fields(self.latest_fields)

    def _apply_map_status(self, fields):
        if {'pose', 'odom', 'best_pic_locs', 'mcl', 'mcl_particles'} & set(fields):
            self.mcl_panel.update_pose(
                self.latest_fields.get('pose'),
                odom_pose=self.latest_fields.get('odom'),
                cnn_locs=self.latest_fields.get('best_pic_locs'),
                mcl_pose=self.latest_fields.get('mcl'),
                mcl_particles=self.latest_fields.get('mcl_particles'),
            )

    def _camera_overlay_text(self):
        cells = self.latest_fields.get('best_pic_cells')
        scores = self.latest_fields.get('best_pic_scores')
        if isinstance(cells, (list, tuple)) and cells:
            score = None
            if isinstance(scores, (list, tuple)) and scores:
                score = self._format_float(scores[0], 1)
            if score is not None:
                return f'CNN: cell {cells[0]} ({score}%)'
            return f'CNN: cell {cells[0]}'
        if 'current_cell' in self.latest_fields:
            return f"Cell: {self.latest_fields['current_cell']}"
        return 'CNN: unknown'

    def _current_yaw_text(self):
        pose = self.latest_fields.get('pose')
        if isinstance(pose, dict) and pose.get('yaw') is not None:
            return self._format_float(pose.get('yaw'), 2)
        odom = self.latest_fields.get('odom')
        if isinstance(odom, (list, tuple)) and len(odom) >= 3:
            return self._format_float(odom[2], 2)
        return 'unknown'

    def _nav_state_text(self):
        mode = self.latest_fields.get('localizer_mode')
        source = self.latest_fields.get('nav_type')
        legacy = self.latest_fields.get('legacy_nav_type')
        match = self.latest_fields.get('match_status')

        if mode and source:
            return f'{mode} / {source}'
        if mode:
            return str(mode)
        if source:
            return str(source)
        if legacy:
            return str(legacy)
        return str(match or 'unknown')

    def _log_status_updates(self, fields):
        if 'best_pic_cells' in fields or 'best_pic_scores' in fields:
            cells = self.latest_fields.get('best_pic_cells')
            scores = self.latest_fields.get('best_pic_scores')
            self._append_log_once('cnn_prediction', f'CNN prediction: cells={cells} scores={scores}')

        tf_status = fields.get('tensorflow_status')
        if tf_status and str(tf_status).lower().startswith('error'):
            self._append_log_once('tensorflow_error', f'TensorFlow/CNN status: {tf_status}')

        rejection = fields.get('cnn_observation_rejected')
        if rejection:
            self._append_log_once('cnn_rejected', f'CNN correction rejected: {rejection}')

        if 'mcl' in fields or 'mcl_variance' in fields:
            self._append_log_once(
                'mcl_update',
                f"MCL update: pose={self._format_sequence(self.latest_fields.get('mcl', 'unknown'))} "
                f"variance={self._format_float(self.latest_fields.get('mcl_variance'), 2)}",
            )

        if 'odom' in fields:
            now = time.time()
            if now - self._last_odom_log_time >= 2.0:
                self._last_odom_log_time = now
                self._append_log_once('odom_update', f"Odometry update: {self._format_sequence(fields['odom'])}")

        if (
            'nav_type' in fields
            or 'legacy_nav_type' in fields
            or 'localizer_mode' in fields
            or 'match_status' in fields
            or 'next_node' in fields
        ):
            self._append_log_once(
                'nav_update',
                f"Navigation update: state={self._nav_state_text()} "
                f"next={self.latest_fields.get('next_node', 'unknown')}",
            )

    def _append_log_once(self, key, message):
        if self._last_log_signatures.get(key) == message:
            return
        self._last_log_signatures[key] = message
        self._append_log(message)

    def _format_sequence(self, value):
        if isinstance(value, (list, tuple)):
            return '[' + ', '.join(self._format_sequence(item) for item in value) + ']'
        if isinstance(value, float):
            return f'{value:.2f}'
        return str(value)

    def _format_float(self, value, digits):
        try:
            return f'{float(value):.{digits}f}'
        except (TypeError, ValueError):
            return str(value)

    def _connect_command_socket(self):
        if self.command_sock is not None:
            return True

        try:
            self.command_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.command_sock.settimeout(0.5)
            self.command_sock.connect((PLANNER_COMMAND_IP, PLANNER_COMMAND_PORT))
            self.command_status_label.setText('Commands: connected')
            self._append_log(f'Command channel connected {PLANNER_COMMAND_IP}:{PLANNER_COMMAND_PORT}')
            return True
        except OSError as error:
            self.command_status_label.setText('Commands: disconnected')
            self._append_log(f'Command channel: {error}')
            if self.command_sock is not None:
                self.command_sock.close()
                self.command_sock = None
            return False

    def _send_command(self, command, fields=None):
        if not self._connect_command_socket():
            return

        try:
            send_command(self.command_sock, command, fields)
            self._append_log(f'Sent command: {command}')
        except OSError as error:
            self._append_log(f'Command send failed: {error}')
            self.command_sock.close()
            self.command_sock = None
            self.command_status_label.setText('Commands: disconnected')

    def _send_start(self):
        self._send_command(
            'set_start',
            {
                'location': self.start_entry.text(),
                'yaw': self.yaw_entry.text(),
            },
        )

    def _send_goal(self):
        self._send_command(
            'set_goal',
            {
                'destination': self.dest_entry.text(),
            },
        )

    def _append_log(self, message):
        timestamp = time.strftime('%H:%M:%S')
        self.log_text.appendPlainText(f'[{timestamp}] {message}')

    def run(self):
        self.show()
        return QtWidgets.QApplication.instance().exec_()

    def closeEvent(self, event):
        self._shutdown()
        event.accept()

    def _shutdown(self):
        self.video_refresh_timer.stop()

        for thread in (self.video_thread, self.status_thread):
            if thread is not None:
                thread.stop()
                thread.wait(1000)

        if self.command_sock is not None:
            try:
                self.command_sock.close()
            except OSError:
                pass
            self.command_sock = None


def frame_to_pixmap(frame):
    if frame is None:
        return QtGui.QPixmap()

    if frame.ndim == 2:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    else:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    rgb_frame = np.ascontiguousarray(rgb_frame)
    height, width, channels = rgb_frame.shape
    bytes_per_line = channels * width
    image = QtGui.QImage(
        rgb_frame.data,
        width,
        height,
        bytes_per_line,
        QtGui.QImage.Format_RGB888,
    ).copy()
    return QtGui.QPixmap.fromImage(image)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = UnifiedSeekerGUI()
    gui.show()
    sys.exit(app.exec_())
