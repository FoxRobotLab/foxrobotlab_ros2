#!/usr/bin/env python3

import os
import queue
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

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
GUI_REFRESH_MS = int(os.environ.get('FOX_GUI_REFRESH_MS', '33'))
FPS_REPORT_PERIOD_SECONDS = float(os.environ.get('FOX_VIDEO_FPS_REPORT_PERIOD', '2.0'))


class UnifiedSeekerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Seeker')
        self.root.geometry('1180x760')
        self.root.protocol('WM_DELETE_WINDOW', self.stop)

        self.running = True
        self.latest_frames = {}
        self.frame_lock = threading.Lock()
        self.event_queue = queue.Queue()
        self.photo_refs = {}
        self.frame_count = 0
        self.last_report_time = time.time()
        self.command_sock = None

        self.connection_status = tk.StringVar(value='Video: waiting')
        self.command_status = tk.StringVar(value='Commands: idle')
        self.video_rate = tk.StringVar(value='0.0 fps')
        self.mode = tk.StringVar(value='Mode: unknown')
        self.battery = tk.StringVar(value='Battery: unknown')
        self.current_node = tk.StringVar(value='Current node: unknown')
        self.current_cell = tk.StringVar(value='Current cell: unknown')
        self.next_node = tk.StringVar(value='Next node: unknown')
        self.match_status = tk.StringVar(value='Match: unknown')
        self.confidence = tk.StringVar(value='Confidence: unknown')
        self.target_distance = tk.StringVar(value='Target distance: unknown')
        self.turn_state = tk.StringVar(value='Turn: unknown')
        self.nav_type = tk.StringVar(value='Nav: unknown')
        self.odom = tk.StringVar(value='Odom: unknown')
        self.last_known = tk.StringVar(value='Last known: unknown')
        self.mcl = tk.StringVar(value='MCL: unknown')
        self.turn_info = tk.StringVar(value='Turn info: unknown')
        self.pic_scores = tk.StringVar(value='Image scores: unknown')
        self.pic_locs = tk.StringVar(value='Image locs: unknown')
        self.tf_status = tk.StringVar(value='TensorFlow: unknown')
        self.tf_version = tk.StringVar(value='TF version: unknown')
        self.gpu_devices = tk.StringVar(value='GPUs: unknown')
        self.cnn_device = tk.StringVar(value='CNN device: unknown')
        self.cnn_model = tk.StringVar(value='CNN model: unknown')
        self.cnn_model_loaded = tk.StringVar(value='Model loaded: unknown')
        self.cnn_latency = tk.StringVar(value='CNN latency: unknown')
        self.cnn_sequence = tk.StringVar(value='Sequence: unknown')
        self.cnn_cells = tk.StringVar(value='Top cells: unknown')
        self.cnn_scores = tk.StringVar(value='Top scores: unknown')
        self.mcl_variance = tk.StringVar(value='MCL variance: unknown')

        self._build_layout()

        self.receiver_thread = threading.Thread(target=self._receive_video, daemon=True)
        self.receiver_thread.start()
        self.status_thread = threading.Thread(target=self._receive_planner_status, daemon=True)
        self.status_thread.start()
        self.root.after(GUI_REFRESH_MS, self._refresh_gui)

    def _build_layout(self):
        self.root.columnconfigure(0, weight=3)
        self.root.columnconfigure(1, weight=2)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=8)
        top.grid(row=0, column=0, columnspan=2, sticky='ew')
        top.columnconfigure(4, weight=1)

        ttk.Label(top, textvariable=self.connection_status).grid(row=0, column=0, padx=(0, 16))
        ttk.Label(top, textvariable=self.command_status).grid(row=0, column=1, padx=(0, 16))
        ttk.Label(top, textvariable=self.video_rate).grid(row=0, column=2, padx=(0, 16))
        ttk.Label(top, textvariable=self.mode).grid(row=0, column=3, padx=(0, 16))
        ttk.Label(top, textvariable=self.battery).grid(row=0, column=4, padx=(0, 16))
        ttk.Button(top, text='Quit', command=self.stop).grid(row=0, column=5)

        video_area = ttk.Frame(self.root, padding=(8, 0, 4, 8))
        video_area.grid(row=1, column=0, sticky='nsew')
        video_area.columnconfigure(0, weight=1)
        video_area.rowconfigure(1, weight=1)
        video_area.rowconfigure(3, weight=1)

        ttk.Label(video_area, text='Camera').grid(row=0, column=0, sticky='w')
        self.camera_label = ttk.Label(video_area)
        self.camera_label.grid(row=1, column=0, sticky='nsew', pady=(2, 10))

        ttk.Label(video_area, text='Depth').grid(row=2, column=0, sticky='w')
        self.depth_label = ttk.Label(video_area)
        self.depth_label.grid(row=3, column=0, sticky='nsew', pady=(2, 0))

        side = ttk.Frame(self.root, padding=(4, 0, 8, 8))
        side.grid(row=1, column=1, sticky='nsew')
        side.columnconfigure(0, weight=1)

        status = ttk.LabelFrame(side, text='Robot Status', padding=8)
        status.grid(row=0, column=0, sticky='ew')
        for idx, variable in enumerate(
            [
                self.current_node,
                self.current_cell,
                self.next_node,
                self.match_status,
                self.confidence,
                self.target_distance,
                self.turn_state,
                self.nav_type,
            ]
        ):
            ttk.Label(status, textvariable=variable).grid(row=idx, column=0, sticky='w', pady=2)

        inputs = ttk.LabelFrame(side, text='Navigation Input', padding=8)
        inputs.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        inputs.columnconfigure(1, weight=1)

        self.start_entry = ttk.Entry(inputs)
        self.yaw_entry = ttk.Entry(inputs)
        self.dest_entry = ttk.Entry(inputs)
        ttk.Label(inputs, text='Start').grid(row=0, column=0, sticky='w', pady=2)
        self.start_entry.grid(row=0, column=1, sticky='ew', pady=2)
        ttk.Label(inputs, text='Yaw').grid(row=1, column=0, sticky='w', pady=2)
        self.yaw_entry.grid(row=1, column=1, sticky='ew', pady=2)
        ttk.Label(inputs, text='Dest').grid(row=2, column=0, sticky='w', pady=2)
        self.dest_entry.grid(row=2, column=1, sticky='ew', pady=2)

        commands = ttk.Frame(inputs)
        commands.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        commands.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(commands, text='Set Start', command=self._send_start).grid(row=0, column=0, sticky='ew', padx=(0, 4))
        ttk.Button(commands, text='Set Goal', command=self._send_goal).grid(row=0, column=1, sticky='ew', padx=4)
        ttk.Button(commands, text='Pause', command=lambda: self._send_command('pause_motors')).grid(row=0, column=2, sticky='ew', padx=(4, 0))

        command_row = ttk.Frame(inputs)
        command_row.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        command_row.columnconfigure((0, 1), weight=1)
        ttk.Button(command_row, text='Run Motors', command=lambda: self._send_command('run_motors')).grid(row=0, column=0, sticky='ew', padx=(0, 4))
        ttk.Button(command_row, text='Quit Robot', command=lambda: self._send_command('quit')).grid(row=0, column=1, sticky='ew', padx=(4, 0))

        telemetry = ttk.LabelFrame(side, text='Localization Telemetry', padding=8)
        telemetry.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        for idx, variable in enumerate(
            [
                self.odom,
                self.last_known,
                self.mcl,
                self.turn_info,
                self.pic_scores,
                self.pic_locs,
            ]
        ):
            ttk.Label(telemetry, textvariable=variable, wraplength=420).grid(row=idx, column=0, sticky='w', pady=2)

        cnn = ttk.LabelFrame(side, text='CNN / TensorFlow', padding=8)
        cnn.grid(row=3, column=0, sticky='ew', pady=(8, 0))
        for idx, variable in enumerate(
            [
                self.tf_status,
                self.tf_version,
                self.gpu_devices,
                self.cnn_device,
                self.cnn_model_loaded,
                self.cnn_latency,
                self.cnn_sequence,
                self.cnn_cells,
                self.cnn_scores,
                self.mcl_variance,
                self.cnn_model,
            ]
        ):
            ttk.Label(cnn, textvariable=variable, wraplength=420).grid(row=idx, column=0, sticky='w', pady=2)

        log_frame = ttk.LabelFrame(side, text='Log', padding=8)
        log_frame.grid(row=4, column=0, sticky='nsew', pady=(8, 0))
        side.rowconfigure(4, weight=1)
        self.log_text = tk.Text(log_frame, height=10, wrap='word')
        self.log_text.pack(fill='both', expand=True)
        self._append_log('Unified GUI ready')

    def _receive_video(self):
        while self.running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    server_socket.bind((VIDEO_HOST, VIDEO_PORT))
                    server_socket.listen(1)
                    self.event_queue.put(('status', f'Video: listening {VIDEO_HOST}:{VIDEO_PORT}'))

                    conn, addr = server_socket.accept()
                    self.event_queue.put(('status', f'Video: connected {addr[0]}'))
                    with conn:
                        while self.running:
                            header, frame = recv_video_frame(conn)
                            stream_name = header['stream']
                            with self.frame_lock:
                                self.latest_frames[stream_name] = frame
                            self.frame_count += 1
                            self._update_fps()

            except (ConnectionError, OSError, ValueError) as error:
                if self.running:
                    self.event_queue.put(('status', 'Video: reconnecting'))
                    self.event_queue.put(('log', f'Video receiver: {error}'))
                    time.sleep(1.0)

    def _receive_planner_status(self):
        while self.running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    server_socket.bind((PLANNER_STATUS_HOST, PLANNER_STATUS_PORT))
                    server_socket.listen(1)
                    self.event_queue.put(
                        (
                            'log',
                            f'Planner status listening {PLANNER_STATUS_HOST}:{PLANNER_STATUS_PORT}',
                        )
                    )

                    conn, addr = server_socket.accept()
                    self.event_queue.put(('log', f'Planner status connected {addr[0]}'))
                    with conn:
                        while self.running:
                            payload = recv_status(conn)
                            self.event_queue.put(('planner_status', payload['fields']))

            except (ConnectionError, OSError, ValueError) as error:
                if self.running:
                    self.event_queue.put(('log', f'Planner status receiver: {error}'))
                    time.sleep(1.0)

    def _update_fps(self):
        now = time.time()
        elapsed = now - self.last_report_time
        if elapsed < FPS_REPORT_PERIOD_SECONDS:
            return

        fps = self.frame_count / elapsed
        self.event_queue.put(('fps', f'{fps:.1f} fps'))
        self.frame_count = 0
        self.last_report_time = now

    def _refresh_gui(self):
        self._process_events()

        with self.frame_lock:
            camera = self.latest_frames.get('camera')
            depth = self.latest_frames.get('depth')

        if camera is not None:
            self._set_label_image(self.camera_label, camera, 'camera')
        if depth is not None:
            self._set_label_image(self.depth_label, depth, 'depth')

        if self.running:
            self.root.after(GUI_REFRESH_MS, self._refresh_gui)

    def _set_label_image(self, label, frame, key):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb_frame)
        photo = ImageTk.PhotoImage(image=image)
        self.photo_refs[key] = photo
        label.configure(image=photo)

    def _process_events(self):
        while True:
            try:
                event_type, value = self.event_queue.get_nowait()
            except queue.Empty:
                return

            if event_type == 'status':
                self.connection_status.set(value)
            elif event_type == 'fps':
                self.video_rate.set(value)
            elif event_type == 'log':
                self._append_log(value)
            elif event_type == 'planner_status':
                self._apply_planner_status(value)

    def _apply_planner_status(self, fields):
        if 'mode' in fields:
            self.mode.set(f"Mode: {fields['mode']}")
        if 'battery' in fields:
            self.battery.set(f"Battery: {fields['battery']}")
        if 'current_node' in fields:
            self.current_node.set(f"Current node: {fields['current_node']}")
        if 'current_cell' in fields:
            self.current_cell.set(f"Current cell: {fields['current_cell']}")
        if 'next_node' in fields:
            self.next_node.set(f"Next node: {fields['next_node']}")
        if 'match_status' in fields:
            self.match_status.set(f"Match: {fields['match_status']}")
        if 'confidence' in fields:
            self.confidence.set(f"Confidence: {float(fields['confidence']):.2f}")
        if 'target_distance' in fields:
            self.target_distance.set(f"Target distance: {float(fields['target_distance']):.2f}")
        if 'turn_state' in fields:
            self.turn_state.set(f"Turn: {fields['turn_state']}")
        if 'nav_type' in fields:
            self.nav_type.set(f"Nav: {fields['nav_type']}")
        if 'odom' in fields:
            self.odom.set(f"Odom: {self._format_sequence(fields['odom'])}")
        if 'last_known' in fields:
            self.last_known.set(f"Last known: {self._format_sequence(fields['last_known'])}")
        if 'mcl' in fields:
            self.mcl.set(f"MCL: {self._format_sequence(fields['mcl'])}")
        if 'turn_info' in fields:
            self.turn_info.set(f"Turn info: {self._format_sequence(fields['turn_info'])}")
        if 'best_pic_scores' in fields:
            self.pic_scores.set(f"Image scores: {self._format_sequence(fields['best_pic_scores'])}")
        if 'best_pic_locs' in fields:
            self.pic_locs.set(f"Image locs: {self._format_sequence(fields['best_pic_locs'])}")
        if 'tensorflow_status' in fields:
            self.tf_status.set(f"TensorFlow: {fields['tensorflow_status']}")
        if 'tensorflow_version' in fields:
            self.tf_version.set(f"TF version: {fields['tensorflow_version']}")
        if 'gpu_devices' in fields:
            self.gpu_devices.set(f"GPUs: {self._format_devices(fields['gpu_devices'])}")
        if 'cnn_device' in fields:
            self.cnn_device.set(f"CNN device: {self._short_device(fields['cnn_device'])}")
        if 'cnn_model' in fields:
            self.cnn_model.set(f"CNN model: {os.path.basename(str(fields['cnn_model']))}")
        if 'cnn_model_loaded' in fields:
            self.cnn_model_loaded.set(f"Model loaded: {fields['cnn_model_loaded']}")
        if 'cnn_latency_ms' in fields:
            self.cnn_latency.set(f"CNN latency: {float(fields['cnn_latency_ms']):.1f} ms")
        if 'cnn_sequence_length' in fields:
            current = fields['cnn_sequence_length']
            target = fields.get('cnn_sequence_target_length', '?')
            self.cnn_sequence.set(f"Sequence: {current}/{target}")
        if 'best_pic_cells' in fields:
            self.cnn_cells.set(f"Top cells: {self._format_sequence(fields['best_pic_cells'])}")
        if 'best_pic_scores' in fields:
            self.cnn_scores.set(f"Top scores: {self._format_sequence(fields['best_pic_scores'])}")
        if 'mcl_variance' in fields:
            self.mcl_variance.set(f"MCL variance: {float(fields['mcl_variance']):.2f}")
        if 'log' in fields:
            self._append_log(fields['log'])

    def _format_sequence(self, value):
        if isinstance(value, (list, tuple)):
            return '[' + ', '.join(self._format_sequence(item) for item in value) + ']'
        if isinstance(value, float):
            return f'{value:.2f}'
        return str(value)

    def _short_device(self, value):
        text = str(value)
        marker = '/device:'
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
            self.command_status.set('Commands: connected')
            self._append_log(f'Command channel connected {PLANNER_COMMAND_IP}:{PLANNER_COMMAND_PORT}')
            return True
        except OSError as error:
            self.command_status.set('Commands: disconnected')
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
            self.command_status.set('Commands: disconnected')

    def _send_start(self):
        self._send_command(
            'set_start',
            {
                'location': self.start_entry.get(),
                'yaw': self.yaw_entry.get(),
            },
        )

    def _send_goal(self):
        self._send_command(
            'set_goal',
            {
                'destination': self.dest_entry.get(),
            },
        )

    def _append_log(self, message):
        timestamp = time.strftime('%H:%M:%S')
        self.log_text.insert('end', f'[{timestamp}] {message}\n')
        self.log_text.see('end')

    def run(self):
        self.root.mainloop()

    def stop(self):
        self.running = False
        if self.command_sock is not None:
            self.command_sock.close()
            self.command_sock = None
        self.root.destroy()


if __name__ == '__main__':
    gui = UnifiedSeekerGUI()
    gui.run()
