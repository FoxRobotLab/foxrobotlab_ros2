#!/usr/bin/env python3

import os
import socket
import sys
import time

import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

FOXROBOTLAB_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if FOXROBOTLAB_SRC not in sys.path:
    sys.path.insert(0, FOXROBOTLAB_SRC)

from client_server.protocol import recv_status, recv_video_frame, send_command


VIDEO_HOST = os.environ.get('FOX_VIDEO_SERVER_HOST', '0.0.0.0')
VIDEO_PORT = int(os.environ.get('FOX_VIDEO_SERVER_PORT', '62028'))
PLANNER_STATUS_HOST = os.environ.get('FOX_GUI_STATUS_SERVER_HOST', '0.0.0.0')
PLANNER_STATUS_PORT = int(os.environ.get('FOX_GUI_STATUS_SERVER_PORT', '62029'))
PLANNER_COMMAND_IP = os.environ.get('FOX_GUI_COMMAND_SERVER_IP', '10.22.21.57')
PLANNER_COMMAND_PORT = int(os.environ.get('FOX_GUI_COMMAND_SERVER_PORT', '62030'))
FPS_REPORT_PERIOD_SECONDS = float(os.environ.get('FOX_VIDEO_FPS_REPORT_PERIOD', '2.0'))


class VideoReceiver(QtCore.QThread):
    frame_received = QtCore.pyqtSignal(str, object)
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
                            self.frame_received.emit(stream_name, frame)
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


class MclVisualization(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super().__init__('MCL', parent)
        self.values = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 22, 16, 16)
        layout.setSpacing(12)

        title = QtWidgets.QLabel('Localization Window')
        title.setObjectName('mclTitle')
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        rows = [
            ('mcl_pose', 'Pose', 'unknown'),
            ('mcl_variance', 'Variance', 'unknown'),
            ('nav_type', 'Nav', 'unknown'),
            ('confidence', 'Confidence', 'unknown'),
            ('current_node', 'Node', 'unknown'),
            ('current_cell', 'Cell', 'unknown'),
        ]
        for row, (key, label, initial) in enumerate(rows):
            name_label = QtWidgets.QLabel(label)
            name_label.setObjectName('fieldName')
            value_label = QtWidgets.QLabel(initial)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            grid.addWidget(name_label, row, 0, QtCore.Qt.AlignTop)
            grid.addWidget(value_label, row, 1)
            self.values[key] = value_label

        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        layout.addStretch(1)

    def set_value(self, key, value):
        if key in self.values:
            self.values[key].setText(str(value))


class UnifiedSeekerGUI(QtWidgets.QMainWindow):
    def __init__(self, start_threads=True):
        super().__init__()
        self.command_sock = None
        self.video_thread = None
        self.status_thread = None

        self.setWindowTitle('Seeker')
        self.resize(1420, 860)
        self.setMinimumSize(1100, 720)
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
        self._build_visual_row(layout)
        self._build_dashboard_row(layout)
        self._build_log(layout)

        layout.setRowStretch(1, 5)
        layout.setRowStretch(2, 3)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 1)

    def _build_top_bar(self, layout):
        top_bar = QtWidgets.QFrame()
        top_bar.setObjectName('topBar')
        top_layout = QtWidgets.QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 8, 12, 8)
        top_layout.setSpacing(18)

        self.video_status_label = QtWidgets.QLabel(f'Video: listening {VIDEO_HOST}:{VIDEO_PORT}')
        self.command_status_label = QtWidgets.QLabel('Commands: idle')
        self.fps_label = QtWidgets.QLabel('0.0 fps')
        self.mode_label = QtWidgets.QLabel('Mode: unknown')
        self.battery_label = QtWidgets.QLabel('Battery: unknown')
        self.quit_button = QtWidgets.QPushButton('Quit')
        self.quit_button.clicked.connect(self.close)

        for label in (
            self.video_status_label,
            self.command_status_label,
            self.fps_label,
            self.mode_label,
            self.battery_label,
        ):
            label.setObjectName('topValue')
            top_layout.addWidget(label)

        top_layout.addStretch(1)
        top_layout.addWidget(self.quit_button)
        layout.addWidget(top_bar, 0, 0, 1, 4)

    def _build_visual_row(self, layout):
        self.depth_panel = ImagePanel('Depth', 'Waiting for depth stream')
        self.camera_panel = ImagePanel('Camera', 'Waiting for camera stream')
        self.mcl_panel = MclVisualization()

        layout.addWidget(self.depth_panel, 1, 0)
        layout.addWidget(self.camera_panel, 1, 1)
        layout.addWidget(self.mcl_panel, 1, 2, 1, 2)

    def _build_dashboard_row(self, layout):
        self.robot_panel = FieldPanel(
            'Robot Status',
            [
                ('current_node', 'Current node', 'unknown'),
                ('current_cell', 'Current cell', 'unknown'),
                ('next_node', 'Next node', 'unknown'),
                ('match_status', 'Match', 'unknown'),
                ('confidence', 'Confidence', 'unknown'),
                ('target_distance', 'Target distance', 'unknown'),
                ('turn_state', 'Turn', 'unknown'),
                ('nav_type', 'Nav', 'unknown'),
            ],
        )
        self.localization_panel = FieldPanel(
            'Localization Telemetry',
            [
                ('odom', 'Odom', 'unknown'),
                ('last_known', 'Last known', 'unknown'),
                ('mcl', 'MCL', 'unknown'),
                ('turn_info', 'Turn info', 'unknown'),
                ('best_pic_scores', 'Image scores', 'unknown'),
                ('best_pic_locs', 'Image locs', 'unknown'),
            ],
        )
        self.controls_panel = self._create_controls_panel()
        self.cnn_panel = FieldPanel(
            'CNN / TensorFlow',
            [
                ('tensorflow_status', 'TensorFlow', 'unknown'),
                ('tensorflow_version', 'TF version', 'unknown'),
                ('gpu_devices', 'GPUs', 'unknown'),
                ('cnn_device', 'CNN device', 'unknown'),
                ('cnn_model_loaded', 'Model loaded', 'unknown'),
                ('cnn_latency_ms', 'CNN latency', 'unknown'),
                ('cnn_sequence_length', 'Sequence', 'unknown'),
                ('best_pic_cells', 'Top cells', 'unknown'),
                ('cnn_scores', 'Top scores', 'unknown'),
                ('predicted_heading', 'Heading', 'unknown'),
                ('heading_source', 'Heading source', 'unknown'),
                ('mcl_variance', 'MCL variance', 'unknown'),
                ('cnn_model', 'CNN model', 'unknown'),
            ],
        )

        layout.addWidget(self.robot_panel, 2, 0)
        layout.addWidget(self.localization_panel, 2, 1)
        layout.addWidget(self.controls_panel, 2, 2)
        layout.addWidget(self.cnn_panel, 2, 3)

    def _create_controls_panel(self):
        panel = QtWidgets.QGroupBox('Navigation Controls')
        layout = QtWidgets.QGridLayout(panel)
        layout.setContentsMargins(12, 18, 12, 12)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        self.start_entry = QtWidgets.QLineEdit()
        self.yaw_entry = QtWidgets.QLineEdit()
        self.dest_entry = QtWidgets.QLineEdit()
        self.start_entry.setPlaceholderText('start node or cell')
        self.yaw_entry.setPlaceholderText('yaw')
        self.dest_entry.setPlaceholderText('destination')

        layout.addWidget(QtWidgets.QLabel('Start'), 0, 0)
        layout.addWidget(self.start_entry, 0, 1, 1, 3)
        layout.addWidget(QtWidgets.QLabel('Yaw'), 1, 0)
        layout.addWidget(self.yaw_entry, 1, 1, 1, 3)
        layout.addWidget(QtWidgets.QLabel('Dest'), 2, 0)
        layout.addWidget(self.dest_entry, 2, 1, 1, 3)

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
            row = 3 + index // 3
            col = index % 3
            span = 1 if index < 3 else 2
            layout.addWidget(button, row, col * span, 1, span)

        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 1)
        return panel

    def _build_log(self, layout):
        log_panel = QtWidgets.QGroupBox('Log')
        log_layout = QtWidgets.QVBoxLayout(log_panel)
        log_layout.setContentsMargins(10, 16, 10, 10)
        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(300)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_panel, 3, 0, 1, 4)

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
            QLabel#mclTitle {
                font-size: 22px;
                font-weight: 700;
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
            '''
        )

    def _start_workers(self):
        self.video_thread = VideoReceiver(self)
        self.video_thread.frame_received.connect(self._set_frame)
        self.video_thread.status_changed.connect(self.video_status_label.setText)
        self.video_thread.fps_changed.connect(self.fps_label.setText)
        self.video_thread.log_message.connect(self._append_log)
        self.video_thread.start()

        self.status_thread = PlannerStatusReceiver(self)
        self.status_thread.status_received.connect(self._apply_planner_status)
        self.status_thread.log_message.connect(self._append_log)
        self.status_thread.start()

    def _set_frame(self, stream_name, frame):
        if stream_name == 'camera':
            self.camera_panel.set_frame(frame)
        elif stream_name == 'depth':
            self.depth_panel.set_frame(frame)

    def _apply_planner_status(self, fields):
        if 'mode' in fields:
            self.mode_label.setText(f"Mode: {fields['mode']}")
        if 'battery' in fields:
            self.battery_label.setText(f"Battery: {fields['battery']}")
        if 'current_node' in fields:
            value = fields['current_node']
            self.robot_panel.set_value('current_node', value)
            self.mcl_panel.set_value('current_node', value)
        if 'current_cell' in fields:
            value = fields['current_cell']
            self.robot_panel.set_value('current_cell', value)
            self.mcl_panel.set_value('current_cell', value)
        if 'next_node' in fields:
            self.robot_panel.set_value('next_node', fields['next_node'])
        if 'match_status' in fields:
            self.robot_panel.set_value('match_status', fields['match_status'])
        if 'confidence' in fields:
            value = self._format_float(fields['confidence'], 2)
            self.robot_panel.set_value('confidence', value)
            self.mcl_panel.set_value('confidence', value)
        if 'target_distance' in fields:
            self.robot_panel.set_value('target_distance', self._format_float(fields['target_distance'], 2))
        if 'turn_state' in fields:
            self.robot_panel.set_value('turn_state', fields['turn_state'])
        if 'nav_type' in fields:
            value = fields['nav_type']
            self.robot_panel.set_value('nav_type', value)
            self.mcl_panel.set_value('nav_type', value)
        if 'odom' in fields:
            self.localization_panel.set_value('odom', self._format_sequence(fields['odom']))
        if 'last_known' in fields:
            self.localization_panel.set_value('last_known', self._format_sequence(fields['last_known']))
        if 'mcl' in fields:
            value = self._format_sequence(fields['mcl'])
            self.localization_panel.set_value('mcl', value)
            self.mcl_panel.set_value('mcl_pose', value)
        if 'turn_info' in fields:
            self.localization_panel.set_value('turn_info', self._format_sequence(fields['turn_info']))
        if 'best_pic_scores' in fields:
            value = self._format_sequence(fields['best_pic_scores'])
            self.localization_panel.set_value('best_pic_scores', value)
            self.cnn_panel.set_value('cnn_scores', value)
        if 'best_pic_locs' in fields:
            self.localization_panel.set_value('best_pic_locs', self._format_sequence(fields['best_pic_locs']))
        if 'tensorflow_status' in fields:
            self.cnn_panel.set_value('tensorflow_status', fields['tensorflow_status'])
        if 'tensorflow_version' in fields:
            self.cnn_panel.set_value('tensorflow_version', fields['tensorflow_version'])
        if 'gpu_devices' in fields:
            self.cnn_panel.set_value('gpu_devices', self._format_devices(fields['gpu_devices']))
        if 'cnn_device' in fields:
            self.cnn_panel.set_value('cnn_device', self._short_device(fields['cnn_device']))
        if 'cnn_model' in fields:
            self.cnn_panel.set_value('cnn_model', os.path.basename(str(fields['cnn_model'])))
        if 'cnn_model_loaded' in fields:
            self.cnn_panel.set_value('cnn_model_loaded', fields['cnn_model_loaded'])
        if 'cnn_latency_ms' in fields:
            self.cnn_panel.set_value('cnn_latency_ms', f"{float(fields['cnn_latency_ms']):.1f} ms")
        if 'cnn_sequence_length' in fields:
            current = fields['cnn_sequence_length']
            target = fields.get('cnn_sequence_target_length', '?')
            self.cnn_panel.set_value('cnn_sequence_length', f'{current}/{target}')
        if 'best_pic_cells' in fields:
            self.cnn_panel.set_value('best_pic_cells', self._format_sequence(fields['best_pic_cells']))
        if 'predicted_heading' in fields:
            self.cnn_panel.set_value('predicted_heading', self._format_float(fields['predicted_heading'], 2))
        if 'heading_source' in fields:
            self.cnn_panel.set_value('heading_source', fields['heading_source'])
        if 'mcl_variance' in fields:
            value = self._format_float(fields['mcl_variance'], 2)
            self.cnn_panel.set_value('mcl_variance', value)
            self.mcl_panel.set_value('mcl_variance', value)
        if 'log' in fields:
            self._append_log(fields['log'])

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

    def _short_device(self, value):
        text = str(value)
        for marker in ('/device:', '/physical_device:'):
            if marker in text:
                return text.split(marker)[-1]
        return text

    def _format_devices(self, value):
        if isinstance(value, (list, tuple)):
            if not value:
                return 'none'
            return ', '.join(self._short_device(item) for item in value)
        return self._short_device(value)

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
