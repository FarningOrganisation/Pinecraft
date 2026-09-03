"""TCP-Client für Pinecraft-LAN-Sitzungen."""

from __future__ import annotations

import queue
import socket
import threading
from typing import Any

from network.protocol import receive_datagram, receive_message, send_datagram, send_message


class LanClient:
    """Client-Transport mit Queue, damit Arcade nie auf Netzwerk-I/O wartet."""

    def __init__(self, sock: socket.socket, welcome: dict[str, Any], host: str):
        self.sock = sock
        self.player_id = str(welcome["player_id"])
        self.seed = int(welcome["seed"])
        self.world_name = str(welcome["world_name"])
        save_data = welcome.get("save_data")
        self.initial_save_data = save_data if isinstance(save_data, dict) else None
        self.incoming: queue.Queue[dict[str, Any]] = queue.Queue()
        self._send_lock = threading.Lock()
        self._next_input_sequence = 0
        self._last_snapshot_sequence = -1
        self._snapshot_lock = threading.Lock()
        self.udp_socket: socket.socket | None = None
        self.udp_token = str(welcome.get("udp_token", ""))
        udp_port = welcome.get("udp_port")
        if self.udp_token and isinstance(udp_port, int) and not isinstance(udp_port, bool):
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                udp_socket.connect((host, udp_port))
                udp_socket.settimeout(0.5)
                self.udp_socket = udp_socket
            except OSError:
                udp_socket.close()
        self._running = threading.Event()
        self._running.set()
        threading.Thread(target=self._receive_loop, name="pinecraft-lan-receive", daemon=True).start()
        if self.udp_socket is not None:
            send_datagram(self.udp_socket, {"type": "udp_hello", "udp_token": self.udp_token})
            threading.Thread(target=self._receive_udp, name="pinecraft-lan-udp", daemon=True).start()

    @classmethod
    def connect(cls, host: str, port: int, name: str, timeout: float = 4.0) -> "LanClient":
        """Verbindet sich und wartet auf die erste Welcome-Nachricht des Hosts."""
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.settimeout(timeout)
        try:
            send_message(sock, {"type": "hello", "name": name})
            welcome = receive_message(sock)
            if welcome is None or welcome.get("type") != "welcome":
                raise ConnectionError("Server did not send a welcome message")
        except Exception:
            sock.close()
            raise
        sock.settimeout(None)
        return cls(sock, welcome, host)

    def send_input(self, left: bool, right: bool, jump: bool) -> int | None:
        """Sendet einen Bewegungszustand und liefert seine Reihenfolgenummer."""
        self._next_input_sequence += 1
        sequence = self._next_input_sequence
        message = {"type": "input", "left": left, "right": right, "jump": jump, "sequence": sequence}
        if self._send_udp(message) or self.send(message):
            return sequence
        return None

    @property
    def is_connected(self) -> bool:
        """True, solange die zuverlässige TCP-Verbindung aktiv ist."""
        return self._running.is_set()

    def send(self, message: dict[str, Any]) -> bool:
        if not self._running.is_set():
            return False
        try:
            with self._send_lock:
                send_message(self.sock, message)
            return True
        except OSError:
            self.close()
            return False

    def drain_messages(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        while True:
            try:
                messages.append(self.incoming.get_nowait())
            except queue.Empty:
                return messages

    def close(self) -> None:
        self._running.clear()
        self.sock.close()
        if self.udp_socket is not None:
            self.udp_socket.close()
            self.udp_socket = None

    def _receive_loop(self) -> None:
        try:
            while self._running.is_set():
                message = receive_message(self.sock)
                if message is None:
                    break
                self._queue_incoming(message)
        except (ConnectionError, OSError, ValueError, UnicodeDecodeError):
            pass
        finally:
            self.close()

    def _send_udp(self, message: dict[str, Any]) -> bool:
        udp_socket = self.udp_socket
        if udp_socket is None or not self._running.is_set():
            return False
        try:
            udp_message = dict(message)
            udp_message["udp_token"] = self.udp_token
            send_datagram(udp_socket, udp_message)
            return True
        except (OSError, ValueError):
            udp_socket.close()
            self.udp_socket = None
            return False

    def _receive_udp(self) -> None:
        udp_socket = self.udp_socket
        if udp_socket is None:
            return
        try:
            while self._running.is_set():
                try:
                    message, _address = receive_datagram(udp_socket)
                except TimeoutError:
                    continue
                self._queue_incoming(message)
        except (OSError, ValueError, UnicodeDecodeError):
            pass

    def _queue_incoming(self, message: dict[str, Any]) -> None:
        if message.get("type") == "snapshot":
            sequence = message.get("snapshot_sequence")
            if isinstance(sequence, int) and not isinstance(sequence, bool):
                with self._snapshot_lock:
                    if sequence <= self._last_snapshot_sequence:
                        return
                    self._last_snapshot_sequence = sequence
        self.incoming.put(message)