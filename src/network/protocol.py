"""Längenpräfixierte JSON-Nachrichten für das Pinecraft-LAN-Protokoll."""

from __future__ import annotations

import json
import socket
import struct
from typing import Any

MAX_MESSAGE_BYTES = 8 * 1024 * 1024
MAX_DATAGRAM_BYTES = 1200


def send_message(sock: socket.socket, message: dict[str, Any]) -> None:
    """Sendet genau eine JSON-Nachricht mit einem 4-Byte-Längenpräfix."""
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError("Network message is too large")
    sock.sendall(struct.pack("!I", len(payload)) + payload)


def send_datagram(sock: socket.socket, message: dict[str, Any], address: tuple[str, int] | None = None) -> None:
    """Sendet eine kleine, einzelne JSON-Nachricht über UDP."""
    payload = _encode_datagram(message)
    if address is None:
        sock.send(payload)
    else:
        sock.sendto(payload, address)


def receive_message(sock: socket.socket) -> dict[str, Any] | None:
    """Empfängt eine Nachricht oder None, wenn die Gegenstelle schließt."""
    header = _receive_exactly(sock, 4)
    if header is None:
        return None
    message_size = struct.unpack("!I", header)[0]
    if message_size <= 0 or message_size > MAX_MESSAGE_BYTES:
        raise ValueError("Invalid network message size")
    payload = _receive_exactly(sock, message_size)
    if payload is None:
        raise ConnectionError("Connection closed while receiving a message")
    message = json.loads(payload.decode("utf-8"))
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise ValueError("Network message must contain a string type")
    return message


def receive_datagram(sock: socket.socket) -> tuple[dict[str, Any], tuple[str, int]]:
    """Empfängt und validiert genau ein UDP-Datagramm."""
    payload, address = sock.recvfrom(MAX_DATAGRAM_BYTES + 1)
    if len(payload) > MAX_DATAGRAM_BYTES:
        raise ValueError("UDP datagram is too large")
    return _decode_datagram(payload), address


def _encode_datagram(message: dict[str, Any]) -> bytes:
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_DATAGRAM_BYTES:
        raise ValueError("UDP datagram is too large")
    return payload


def _decode_datagram(payload: bytes) -> dict[str, Any]:
    message = json.loads(payload.decode("utf-8"))
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise ValueError("Network message must contain a string type")
    return message


def _receive_exactly(sock: socket.socket, size: int) -> bytes | None:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            if not chunks:
                return None
            raise ConnectionError("Connection closed while receiving a message")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)