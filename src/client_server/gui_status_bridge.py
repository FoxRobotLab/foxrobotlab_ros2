#!/usr/bin/env python3

import queue
import socket
import threading
import time

from client_server.protocol import recv_command, send_status


class GuiStatusBridge:
    def __init__(
        self,
        legacy_gui,
        server_ip,
        port,
        enabled=True,
        timeout=0.2,
        command_host='0.0.0.0',
        command_port=62030,
        command_enabled=True,
    ):
        self.legacy_gui = legacy_gui
        self.enabled = enabled
        self.server_ip = server_ip
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.command_enabled = command_enabled
        self.command_host = command_host
        self.command_port = command_port
        self.command_queue = queue.Queue()
        self.pending_start = None
        self.pending_goal = None
        self.command_running = False

        if not enabled:
            return

        self._connect_status_socket()

        if command_enabled:
            self.command_running = True
            self.command_thread = threading.Thread(target=self._run_command_server, daemon=True)
            self.command_thread.start()

    def __getattr__(self, name):
        return getattr(self.legacy_gui, name)

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        self.command_running = False

    def _send(self, fields):
        if not self.enabled:
            return

        if self.sock is None:
            self._connect_status_socket()
        if self.sock is None:
            return

        try:
            send_status(self.sock, fields)
        except OSError as error:
            print(f'GUI status bridge disconnected: {error}')
            self.sock.close()
            self.sock = None

    def _connect_status_socket(self):
        if self.sock is not None:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.server_ip, self.port))
            print(f'GUI status bridge connected: {self.server_ip}:{self.port}')
            return True
        except OSError as error:
            print(f'GUI status bridge waiting: {error}')
            self.sock = None
            return False

    def _run_command_server(self):
        while self.command_running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    server_socket.bind((self.command_host, self.command_port))
                    server_socket.listen(1)
                    self._send({'log': f'GUI command server listening {self.command_host}:{self.command_port}'})

                    conn, addr = server_socket.accept()
                    self._send({'log': f'GUI command connected {addr[0]}'})
                    with conn:
                        while self.command_running:
                            payload = recv_command(conn)
                            self._handle_command(payload)
            except (ConnectionError, OSError, ValueError) as error:
                if self.command_running:
                    print(f'GUI command server reconnecting: {error}')
                    time.sleep(1.0)

    def _handle_command(self, payload):
        command = payload['command']
        fields = payload.get('fields', {})

        if command in ('set_start', 'set_goal'):
            if command == 'set_start':
                self.pending_start = fields
            else:
                self.pending_goal = fields
            self.command_queue.put(payload)
            self._send({'log': f'Received {command}: {fields}'})
        elif command == 'pause_motors':
            self.legacy_gui.turtleBot.pauseMovement()
            self._send({'log': 'Motors paused from unified GUI'})
        elif command == 'run_motors':
            self.legacy_gui.turtleBot.unpauseMovement()
            self._send({'log': 'Motors resumed from unified GUI'})
        elif command == 'toggle_motors':
            self.legacy_gui.toggleMotors()
            self._send({'log': 'Motors toggled from unified GUI'})
        elif command == 'quit':
            self._send({'log': 'Quit requested from unified GUI'})
            self.legacy_gui.quitProgram()
        else:
            self._send({'log': f'Unknown GUI command: {command}'})

    def _wait_for_command(self, command):
        while self.command_running:
            payload = self.command_queue.get()
            if payload['command'] == command:
                return payload.get('fields', {})

        raise RuntimeError(f'GUI command server stopped while waiting for {command}')

    def popupStart(self):
        if not self.command_enabled:
            return self.legacy_gui.popupStart()

        self._send({'log': 'Waiting for start location from unified GUI'})
        fields = self._wait_for_command('set_start')
        self.pending_start = fields

    def inputStartLoc(self):
        if not self.command_enabled:
            return self.legacy_gui.inputStartLoc()

        if self.pending_start is None:
            self.pending_start = self._wait_for_command('set_start')
        return str(self.pending_start.get('location', ''))

    def inputStartYaw(self):
        if not self.command_enabled:
            return self.legacy_gui.inputStartYaw()

        if self.pending_start is None:
            self.pending_start = self._wait_for_command('set_start')
        yaw = str(self.pending_start.get('yaw', ''))
        self.pending_start = None
        return yaw

    def popupDest(self):
        if not self.command_enabled:
            return self.legacy_gui.popupDest()

        self._send({'log': 'Waiting for destination from unified GUI'})
        fields = self._wait_for_command('set_goal')
        self.pending_goal = fields

    def inputDes(self):
        if not self.command_enabled:
            return self.legacy_gui.inputDes()

        if self.pending_goal is None:
            self.pending_goal = self._wait_for_command('set_goal')
        destination = str(self.pending_goal.get('destination', ''))
        self.pending_goal = None
        return destination

    def updateNextNode(self, node):
        self._send({'next_node': node})
        return self.legacy_gui.updateNextNode(node)

    def updateCNode(self, closestNode):
        self._send({'current_node': closestNode})
        return self.legacy_gui.updateCNode(closestNode)

    def updateMatchStatus(self, status):
        self._send({'match_status': status})
        return self.legacy_gui.updateMatchStatus(status)

    def updateTDist(self, dist):
        self._send({'target_distance': dist})
        return self.legacy_gui.updateTDist(dist)

    def updateTurnState(self, statement):
        self._send({'turn_state': statement})
        return self.legacy_gui.updateTurnState(statement)

    def updateTurnInfo(self, turnData):
        self._send({'turn_info': turnData})
        return self.legacy_gui.updateTurnInfo(turnData)

    def updateOdomList(self, loc):
        self._send({'odom': loc})
        return self.legacy_gui.updateOdomList(loc)

    def updateLastKnownList(self, loc):
        self._send({'last_known': loc})
        return self.legacy_gui.updateLastKnownList(loc)

    def updateMCLList(self, loc):
        self._send({'mcl': loc})
        return self.legacy_gui.updateMCLList(loc)

    def updatePicLocs(self, loc1, loc2, loc3):
        self._send({'best_pic_locs': [loc1, loc2, loc3]})
        return self.legacy_gui.updatePicLocs(loc1, loc2, loc3)

    def updatePicConf(self, scores):
        self._send({'best_pic_scores': scores})
        return self.legacy_gui.updatePicConf(scores)

    def updateNavType(self, nav_type):
        self._send({'nav_type': nav_type})
        return self.legacy_gui.updateNavType(nav_type)

    def navigatingMode(self):
        self._send({'mode': 'Navigating'})
        return self.legacy_gui.navigatingMode()

    def localizingMode(self):
        self._send({'mode': 'Localizing'})
        return self.legacy_gui.localizingMode()

    def updateMessageText(self, text):
        self._send({'log': text})
        return self.legacy_gui.updateMessageText(text)

    def stop(self):
        try:
            return self.legacy_gui.stop()
        finally:
            self.close()
