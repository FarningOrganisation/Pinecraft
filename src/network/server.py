"""Kleiner TCP-Server, der Client-Nachrichten an den Spielthread weitergibt."""

from __future__ import annotations

import queue
import socket
import threading
import uuid
from dataclasses import dataclass
from typing import Any

from network.protocol import receive_datagram, receive_message, send_datagram, send_message


def get_local_ipv4() -> str:
    """Ermittelt die bevorzugte lokale IPv4-Adresse ohne Daten zu senden."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return str(probe.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


@dataclass
class _ConnectedClient:
    player_id: str
    name: str
    sock: socket.socket
    send_lock: threading.Lock
    udp_token: str
    udp_address: tuple[str, int] | None = None


class LanServer:
    """Transportserver; die GameView bleibt für Welt und Physik autoritativ."""

    def __init__(self, seed: int, world_name: str, port: int = 25565, initial_save_data: dict[str, Any] | None = None):
        self.seed = int(seed)
        self.world_name = world_name
        self.port = int(port)
        self.initial_save_data = initial_save_data
        self.incoming: queue.Queue[dict[str, Any]] = queue.Queue()
        self._clients: dict[str, _ConnectedClient] = {}
        self._clients_lock = threading.Lock()
        self._running = threading.Event()
        self._listen_socket: socket.socket | None = None
        self._udp_socket: socket.socket | None = None
        self._snapshot_sequence = 0
        self.local_ipv4 = "127.0.0.1"

    @property
    def is_running(self) -> bool:
        """True, solange Listener und UDP-Socket aktiv sind."""
        return self._running.is_set()

    def start(self) -> None:
        """Startet den Listener auf allen IPv4-Netzwerkschnittstellen."""
        if self._running.is_set():
            return
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(("0.0.0.0", self.port))
        listen_socket.listen()
        listen_socket.settimeout(0.5)
        self.port = int(listen_socket.getsockname()[1])
        self.local_ipv4 = get_local_ipv4()
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_socket.bind(("0.0.0.0", self.port))
        except OSError:
            listen_socket.close()
            udp_socket.close()
            raise
        udp_socket.settimeout(0.5)
        self._listen_socket = listen_socket
        self._udp_socket = udp_socket
        self._running.set()
        threading.Thread(target=self._accept_loop, name="pinecraft-lan-accept", daemon=True).start()
        threading.Thread(target=self._receive_udp, name="pinecraft-lan-udp", daemon=True).start()

    def stop(self) -> None:
        """Schließt Listener und alle verbundenen Clients."""
        self._running.clear()
        if self._listen_socket is not None:
            self._listen_socket.close()
            self._listen_socket = None
        if self._udp_socket is not None:
            self._udp_socket.close()
            self._udp_socket = None
        with self._clients_lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            client.sock.close()

    def drain_messages(self) -> list[dict[str, Any]]:
        """Liefert alle seit dem letzten Frame empfangenen Client-Nachrichten."""
        messages: list[dict[str, Any]] = []
        while True:
            try:
                messages.append(self.incoming.get_nowait())
            except queue.Empty:
                return messages

    def broadcast(self, message: dict[str, Any]) -> None:
        """Sendet eine Nachricht an alle verbundenen Clients."""
        with self._clients_lock:
            clients = list(self._clients.values())
        for client in clients:
            try:
                with client.send_lock:
                    send_message(client.sock, message)
            except OSError:
                self._disconnect(client.player_id)

    def broadcast_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Sendet einen Snapshot bevorzugt über UDP, sonst zuverlässig über TCP."""
        self._snapshot_sequence += 1
        message = dict(snapshot)
        message["snapshot_sequence"] = self._snapshot_sequence
        with self._clients_lock:
            clients = list(self._clients.values())
        for client in clients:
            udp_socket = self._udp_socket
            if udp_socket is not None and client.udp_address is not None:
                try:
                    send_datagram(udp_socket, message, client.udp_address)
                    continue
                except ValueError:
                    pass
                except OSError:
                    continue
            try:
                with client.send_lock:
                    send_message(client.sock, message)
            except OSError:
                self._disconnect(client.player_id)

    def _accept_loop(self) -> None:
        assert self._listen_socket is not None
        while self._running.is_set():
            try:
                client_socket, _address = self._listen_socket.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            client_socket.settimeout(5.0)
            threading.Thread(
                target=self._receive_client,
                args=(client_socket,),
                name="pinecraft-lan-client",
                daemon=True,
            ).start()

    def _receive_client(self, client_socket: socket.socket) -> None:
        player_id: str | None = None
        try:
            hello = receive_message(client_socket)
            if hello is None or hello.get("type") != "hello":
                return
            name = str(hello.get("name", "Player")).strip()[:24] or "Player"
            player_id = uuid.uuid4().hex
            udp_token = uuid.uuid4().hex
            client = _ConnectedClient(player_id, name, client_socket, threading.Lock(), udp_token)
            with self._clients_lock:
                self._clients[player_id] = client
            welcome: dict[str, Any] = {
                "type": "welcome",
                "player_id": player_id,
                "seed": self.seed,
                "world_name": self.world_name,
                "udp_port": self.port,
                "udp_token": udp_token,
            }
            if self.initial_save_data is not None:
                welcome["save_data"] = self.initial_save_data
            with client.send_lock:
                send_message(client_socket, welcome)
            self.incoming.put({"type": "player_joined", "player_id": player_id, "name": name})
            client_socket.settimeout(None)
            while self._running.is_set():
                message = receive_message(client_socket)
                if message is None:
                    break
                if message.get("type") == "input":
                    message["player_id"] = player_id
                    self.incoming.put(message)
        except (ConnectionError, OSError, ValueError, UnicodeDecodeError):
            pass
        finally:
            if player_id is not None:
                self._disconnect(player_id)
            else:
                client_socket.close()

    def _receive_udp(self) -> None:
        """Ordnet UDP-Datagramme per Token einem TCP-Client zu."""
        assert self._udp_socket is not None
        while self._running.is_set():
            try:
                message, address = receive_datagram(self._udp_socket)
            except TimeoutError:
                continue
            except (OSError, ValueError, UnicodeDecodeError):
                continue

            token = message.get("udp_token")
            if not isinstance(token, str):
                continue
            with self._clients_lock:
                client = next((candidate for candidate in self._clients.values() if candidate.udp_token == token), None)
                if client is not None:
                    client.udp_address = address
            if client is None or message.get("type") != "input":
                continue
            message["player_id"] = client.player_id
            self.incoming.put(message)

    def _disconnect(self, player_id: str) -> None:
        with self._clients_lock:
            client = self._clients.pop(player_id, None)
        if client is not None:
            client.sock.close()
            self.incoming.put({"type": "player_left", "player_id": player_id})