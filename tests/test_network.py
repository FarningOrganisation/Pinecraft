import socket
import sys
import threading
import time
import unittest
import queue
from pathlib import Path
from unittest.mock import patch

import arcade

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from network.client import LanClient
from network.protocol import receive_datagram, receive_message, send_datagram, send_message
from network.server import LanServer
from game import GameView
from player import Player
from physics import AABBPhysics
from settings import TILE_SIZE
from world import World


class NetworkProtocolTests(unittest.TestCase):
    def test_framed_json_round_trip(self):
        sender, receiver = socket.socketpair()
        try:
            send_message(sender, {"type": "input", "left": True})
            self.assertEqual(receive_message(receiver), {"type": "input", "left": True})
        finally:
            sender.close()
            receiver.close()

    def test_udp_json_datagram_round_trip(self):
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        try:
            send_datagram(sender, {"type": "input", "sequence": 1}, receiver.getsockname())
            message, _address = receive_datagram(receiver)
            self.assertEqual(message, {"type": "input", "sequence": 1})
        finally:
            sender.close()
            receiver.close()


class LanServerTests(unittest.TestCase):
    def setUp(self):
        self.save_data = {
            "meta": {"world_name": "LanTest"},
            "world": {"seed": 1234, "changed_blocks": {"0": [[1, 2, 3]]}},
            "padding": "x" * (128 * 1024),
        }
        self.server = LanServer(seed=1234, world_name="LanTest", port=0, initial_save_data=self.save_data)
        self.server.start()
        self.client = LanClient.connect("127.0.0.1", self.server.port, "Ada")

    def tearDown(self):
        self.client.close()
        self.server.stop()

    def _wait_for_server_message(self, message_type: str) -> dict:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            for message in self.server.drain_messages():
                if message.get("type") == message_type:
                    return message
            threading.Event().wait(0.01)
        self.fail(f"Server did not receive {message_type!r}")

    def _wait_for_client_message(self, message_type: str) -> dict:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            for message in self.client.drain_messages():
                if message.get("type") == message_type:
                    return message
            threading.Event().wait(0.01)
        self.fail(f"Client did not receive {message_type!r}")

    def _wait_for_udp_registration(self) -> None:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            with self.server._clients_lock:
                client = self.server._clients.get(self.client.player_id)
                if client is not None and client.udp_address is not None:
                    return
            threading.Event().wait(0.01)
        self.fail("Client did not register its UDP address")

    def test_handshake_provides_host_world_data(self):
        joined = self._wait_for_server_message("player_joined")
        self.assertEqual(joined["name"], "Ada")
        self.assertEqual(joined["player_id"], self.client.player_id)
        self.assertEqual(self.client.seed, 1234)
        self.assertEqual(self.client.world_name, "LanTest")
        self.assertEqual(self.client.initial_save_data, self.save_data)
        self.assertIsNotNone(self.client.udp_socket)

    def test_client_input_is_forwarded_with_server_player_id(self):
        self._wait_for_server_message("player_joined")
        self.client.send_input(left=True, right=False, jump=True)
        message = self._wait_for_server_message("input")
        self.assertEqual(message["player_id"], self.client.player_id)
        self.assertEqual(message["sequence"], 1)
        self.assertTrue(message["left"])
        self.assertTrue(message["jump"])

    def test_server_broadcast_reaches_client(self):
        self._wait_for_server_message("player_joined")
        self.server.broadcast({"type": "snapshot", "players": []})
        self.assertEqual(self._wait_for_client_message("snapshot"), {"type": "snapshot", "players": []})

    def test_udp_snapshot_reaches_registered_client(self):
        self._wait_for_server_message("player_joined")
        self._wait_for_udp_registration()

        self.server.broadcast_snapshot({"type": "snapshot", "players": []})

        snapshot = self._wait_for_client_message("snapshot")
        self.assertEqual(snapshot["players"], [])
        self.assertEqual(snapshot["snapshot_sequence"], 1)

    def test_client_disconnects_when_host_stops(self):
        self._wait_for_server_message("player_joined")
        self.server.stop()

        deadline = time.monotonic() + 1.0
        while self.client.is_connected and time.monotonic() < deadline:
            threading.Event().wait(0.01)
        self.assertFalse(self.client.is_connected)

    def test_large_snapshot_falls_back_to_tcp(self):
        self._wait_for_server_message("player_joined")
        self._wait_for_udp_registration()

        self.server.broadcast_snapshot({"type": "snapshot", "players": [], "padding": "x" * 1200})

        snapshot = self._wait_for_client_message("snapshot")
        self.assertEqual(snapshot["padding"], "x" * 1200)


class GameViewLanSessionTests(unittest.TestCase):
    def test_lost_client_closes_lan_session_and_returns_to_start(self):
        class ClientStub:
            is_connected = False

            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        class ServerStub:
            is_running = True

            def __init__(self):
                self.stopped = False

            def stop(self):
                self.stopped = True

        class WindowStub:
            def __init__(self):
                self.shown_view = None

            def show_view(self, view):
                self.shown_view = view

        client = ClientStub()
        server = ServerStub()
        window = WindowStub()
        view = GameView.__new__(GameView)
        view.lan_client = client
        view.lan_server = server
        view.window = window

        with patch("start_menu_view.StartMenuView", return_value="start-menu"):
            disconnected = view._disconnect_if_lan_ended()

        self.assertTrue(disconnected)
        self.assertTrue(client.closed)
        self.assertTrue(server.stopped)
        self.assertIsNone(view.lan_client)
        self.assertIsNone(view.lan_server)
        self.assertEqual(window.shown_view, "start-menu")


class JoinedClientUpdateTests(unittest.TestCase):
    def test_client_waits_for_host_snapshot_without_running_physics(self):
        class ClientStub:
            def send_input(self, left, right, jump):
                self.inputs = (left, right, jump)

        class PhysicsStub:
            def update(self, player, delta_time):
                raise AssertionError("A joined client must not run local physics")

        view = GameView.__new__(GameView)
        view.lan_client = ClientStub()
        view.left_pressed = True
        view.right_pressed = False
        view.jump_pressed = False
        view._network_last_input = None
        view._has_network_snapshot = False
        view.physics = PhysicsStub()

        view._update_joined_client(1 / 60)

        self.assertEqual(view.lan_client.inputs, (True, False, False))

    def test_snapshot_synchronizes_and_advances_animation_state(self):
        view = GameView.__new__(GameView)
        view.local_player_id = "client"
        view.player = Player(World(seed=1234))
        view.remote_players = {}
        view.remote_player_sprite_list = arcade.SpriteList()
        view._remote_player_targets = {}
        view._pending_network_inputs = []
        view._has_network_snapshot = False

        view._apply_network_snapshot(
            {
                "players": [
                    {
                        "id": "client",
                        "x": 100.0,
                        "y": 200.0,
                        "vx": 220.0,
                        "vy": 0.0,
                        "facing_right": True,
                        "on_ground": True,
                        "animation_state": "walking",
                    }
                ]
            }
        )
        view._update_network_player_animations(0.3)

        self.assertTrue(view._has_network_snapshot)
        self.assertEqual(view.player.current_animation_state, "walking")
        self.assertEqual(view.player.current_animation.frame_index, 1)

    def test_snapshot_acknowledgement_discards_confirmed_input(self):
        view = GameView.__new__(GameView)
        view.local_player_id = "client"
        view.player = Player(World(seed=1234))
        view.remote_players = {}
        view.remote_player_sprite_list = arcade.SpriteList()
        view._remote_player_targets = {}
        view._pending_network_inputs = [(1, True, False, False, 1 / 60)]
        view._has_network_snapshot = False

        view._apply_network_snapshot(
            {"players": [{"id": "client", "x": 100.0, "y": 200.0, "input_sequence": 1}]}
        )

        self.assertEqual(view._pending_network_inputs, [])
        self.assertEqual((view.player.center_x, view.player.center_y), (100.0, 200.0))

    def test_unconfirmed_input_is_replayed_after_snapshot(self):
        view = GameView.__new__(GameView)
        view.local_player_id = "client"
        view.world = World(seed=1234)
        view.player = Player(view.world)
        spawn_x, spawn_y = view._default_spawn_point()
        view.player.center_x = spawn_x
        view.player.center_y = spawn_y
        view.player.on_ground = True
        view.world.update_loaded_chunks(spawn_x)
        view.physics = AABBPhysics(view.world)
        view.remote_players = {}
        view.remote_player_sprite_list = arcade.SpriteList()
        view._remote_player_targets = {}
        view._pending_network_inputs = [(2, False, True, False, 1 / 60)]
        view._has_network_snapshot = False

        view._apply_network_snapshot(
            {
                "players": [
                    {"id": "client", "x": spawn_x, "y": spawn_y, "on_ground": True, "input_sequence": 1}
                ]
            }
        )

        self.assertEqual(view._pending_network_inputs, [(2, False, True, False, 1 / 60)])
        self.assertGreater(view.player.center_x, spawn_x)

    def test_prediction_waits_for_collision_chunks(self):
        class PhysicsStub:
            def update(self, player, delta_time):
                raise AssertionError("Prediction must wait for collision chunks")

        view = GameView.__new__(GameView)
        view.world = World(seed=1234)
        view.player = Player(view.world)
        view.world.chunks = {}
        view.physics = PhysicsStub()

        view._simulate_predicted_input(left=False, right=True, jump=False, delta_time=1 / 60)

    def test_remote_player_position_is_interpolated(self):
        view = GameView.__new__(GameView)
        view.local_player_id = "client"
        view.player = Player(World(seed=1234))
        remote = Player(view.player.world)
        remote.center_x = 100.0
        remote.center_y = 200.0
        view.remote_players = {"host": remote}
        view.remote_player_sprite_list = arcade.SpriteList()
        view._remote_player_targets = {"host": (200.0, 300.0)}

        view._interpolate_remote_players(1 / 60)

        self.assertGreater(remote.center_x, 100.0)
        self.assertLess(remote.center_x, 200.0)
        self.assertGreater(remote.center_y, 200.0)
        self.assertLess(remote.center_y, 300.0)

    def test_host_snapshot_acknowledges_latest_remote_input(self):
        class ServerStub:
            def broadcast_snapshot(self, message):
                self.message = message

        view = GameView.__new__(GameView)
        view.world = World(seed=1234)
        view.player = Player(view.world)
        remote = Player(view.world)
        view.remote_players = {"client": remote}
        view.remote_player_inputs = {"client": {"left": False, "right": True, "jump": False, "sequence": 7}}
        view.lan_server = ServerStub()
        view._network_snapshot_timer = 0.0

        view._send_network_snapshot(1 / 20, [])

        self.assertEqual(view.lan_server.message["players"][1]["input_sequence"], 7)

    def test_initial_spawn_avoids_ocean_water(self):
        for seed in (1, 43211, 99999):
            view = GameView.__new__(GameView)
            view.world = World(seed=seed)
            view.player = Player(view.world)

            spawn_x, spawn_y = view._default_spawn_point()
            spawn_water_tile = int((spawn_y - view.player.collision_height / 2) // TILE_SIZE)

            self.assertLess(
                view.world.get_water(int(spawn_x // TILE_SIZE), spawn_water_tile),
                Player.WATER_CONTACT_THRESHOLD,
            )


class LanClientSnapshotTests(unittest.TestCase):
    def test_stale_udp_snapshot_is_discarded(self):
        client = LanClient.__new__(LanClient)
        client.incoming = queue.Queue()
        client._last_snapshot_sequence = -1
        client._snapshot_lock = threading.Lock()

        client._queue_incoming({"type": "snapshot", "snapshot_sequence": 2, "players": []})
        client._queue_incoming({"type": "snapshot", "snapshot_sequence": 1, "players": []})

        self.assertEqual(client.drain_messages(), [{"type": "snapshot", "snapshot_sequence": 2, "players": []}])


if __name__ == "__main__":
    unittest.main()