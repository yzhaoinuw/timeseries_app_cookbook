# -*- coding: utf-8 -*-
"""Tests for multi-session (multiple app windows) support: slot claiming,
the env-driven config contract, the peer current-file endpoint, and the
same-file load refusal (COOKBOOK recipe 17)."""

import importlib
import json
import socket
from unittest.mock import MagicMock
from urllib.error import URLError

import dash

import run_desktop_app


def _bind_ephemeral_socket():
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("127.0.0.1", 0))
    return holder, holder.getsockname()[1]


class TestClaimSessionSlot:
    def test_claims_slot_zero_when_base_port_is_free(self):
        holder, port = _bind_ephemeral_socket()
        holder.close()  # freed port becomes the base of an all-free slot range

        slot, claimed_port, probe_socket = run_desktop_app.claim_session_slot(
            base_port=port, max_sessions=3
        )

        try:
            assert (slot, claimed_port) == (0, port)
            assert probe_socket.getsockname() == ("127.0.0.1", port)
        finally:
            probe_socket.close()

    def test_skips_occupied_slot_and_claims_next(self):
        holder, base_port = _bind_ephemeral_socket()

        try:
            slot, claimed_port, probe_socket = run_desktop_app.claim_session_slot(
                base_port=base_port, max_sessions=3
            )
            try:
                assert (slot, claimed_port) == (1, base_port + 1)
            finally:
                probe_socket.close()
        finally:
            holder.close()

    def test_returns_none_when_all_slots_are_taken(self):
        holder, base_port = _bind_ephemeral_socket()

        try:
            result = run_desktop_app.claim_session_slot(base_port=base_port, max_sessions=1)
        finally:
            holder.close()

        assert result == (None, None, None)


def _reload_config():
    import ts_app.config

    return importlib.reload(ts_app.config)


class TestConfigEnvContract:
    """ts_app.config reads the slot and peer ports exported by the launcher."""

    def test_defaults_to_slot_zero_with_no_peers(self, monkeypatch):
        monkeypatch.delenv("TS_APP_INSTANCE_SLOT", raising=False)
        monkeypatch.delenv("TS_APP_PEER_PORTS", raising=False)
        try:
            config = _reload_config()
            assert config.INSTANCE_SLOT == 0
            assert config.PEER_PORTS == []
        finally:
            monkeypatch.undo()
            _reload_config()

    def test_reads_slot_and_peer_ports(self, monkeypatch):
        monkeypatch.setenv("TS_APP_INSTANCE_SLOT", "1")
        monkeypatch.setenv("TS_APP_PEER_PORTS", "8060,8062")
        try:
            config = _reload_config()
            assert config.INSTANCE_SLOT == 1
            assert config.PEER_PORTS == [8060, 8062]
        finally:
            monkeypatch.undo()
            _reload_config()

    def test_ignores_malformed_env_values(self, monkeypatch):
        monkeypatch.setenv("TS_APP_INSTANCE_SLOT", "not-a-slot")
        monkeypatch.setenv("TS_APP_PEER_PORTS", "abc, 8061 ,,")
        try:
            config = _reload_config()
            assert config.INSTANCE_SLOT == 0
            assert config.PEER_PORTS == [8061]
        finally:
            monkeypatch.undo()
            _reload_config()

    def test_later_window_forces_profiling_off(self, monkeypatch):
        monkeypatch.setenv("TS_APP_INSTANCE_SLOT", "2")
        monkeypatch.setenv("TS_APP_PROFILE_NAV", "1")
        try:
            config = _reload_config()
            assert config.PROFILE_NAVIGATION is False
        finally:
            monkeypatch.undo()
            _reload_config()


class TestCurrentFileEndpoint:
    def _client(self, monkeypatch, filepath):
        import ts_app.app as app_module

        monkeypatch.setattr(app_module, "_current_filepath", filepath)
        return app_module.app.server.test_client()

    def test_reports_open_file(self, monkeypatch):
        client = self._client(monkeypatch, "/data/recording.npz")

        response = client.get("/_ts_app/current-file")

        assert response.get_json() == {"app": "ts_app", "filepath": "/data/recording.npz"}

    def test_reports_empty_string_when_no_file_open(self, monkeypatch):
        client = self._client(monkeypatch, None)

        response = client.get("/_ts_app/current-file")

        assert response.get_json() == {"app": "ts_app", "filepath": ""}

    def test_fresh_process_ignores_stale_cached_filepath(self, monkeypatch):
        """A restarted slot reuses its cache dir, where filepath persists for
        days; the endpoint must not report it before a file is opened here."""
        import ts_app.app as app_module

        fake_cache = MagicMock()
        fake_cache.get.return_value = "/data/stale.npz"
        monkeypatch.setattr(app_module, "cache", fake_cache)
        client = self._client(monkeypatch, None)

        response = client.get("/_ts_app/current-file")

        assert response.get_json() == {"app": "ts_app", "filepath": ""}

    def test_initialize_state_updates_process_state(self, monkeypatch):
        import ts_app.app as app_module

        monkeypatch.setattr(app_module, "_current_filepath", None)
        monkeypatch.setattr(app_module, "cache", MagicMock())
        monkeypatch.setattr(app_module, "clear_temp_artifacts", lambda keep_stem: None)
        monkeypatch.setattr(app_module, "clear_fig_resamplers", lambda: None)

        app_module.initialize_state("/data/recording.npz")

        assert app_module.get_current_filepath() == "/data/recording.npz"


class _FakeResponse:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode()

    def read(self, *args):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestFindPeerSessionWithFile:
    def test_returns_port_when_peer_has_same_file(self, monkeypatch):
        import ts_app.app as app_module

        monkeypatch.setattr(app_module, "PEER_PORTS", [8061])
        monkeypatch.setattr(
            app_module,
            "urlopen",
            lambda url, timeout: _FakeResponse(
                {"app": "ts_app", "filepath": "/data/./recording.npz"}
            ),
        )

        assert app_module.find_peer_session_with_file("/data/recording.npz") == 8061

    def test_returns_none_when_peer_has_different_file(self, monkeypatch):
        import ts_app.app as app_module

        monkeypatch.setattr(app_module, "PEER_PORTS", [8061])
        monkeypatch.setattr(
            app_module,
            "urlopen",
            lambda url, timeout: _FakeResponse({"app": "ts_app", "filepath": "/data/other.npz"}),
        )

        assert app_module.find_peer_session_with_file("/data/recording.npz") is None

    def test_skips_dead_peer_and_checks_next(self, monkeypatch):
        import ts_app.app as app_module

        def fake_urlopen(url, timeout):
            if ":8060/" in url:
                raise URLError("connection refused")
            return _FakeResponse({"app": "ts_app", "filepath": "/data/recording.npz"})

        monkeypatch.setattr(app_module, "PEER_PORTS", [8060, 8062])
        monkeypatch.setattr(app_module, "urlopen", fake_urlopen)

        assert app_module.find_peer_session_with_file("/data/recording.npz") == 8062

    def test_ignores_non_app_listener_on_peer_port(self, monkeypatch):
        import ts_app.app as app_module

        monkeypatch.setattr(app_module, "PEER_PORTS", [8061])
        monkeypatch.setattr(
            app_module,
            "urlopen",
            lambda url, timeout: _FakeResponse({"filepath": "/data/recording.npz"}),
        )

        assert app_module.find_peer_session_with_file("/data/recording.npz") is None

    def test_no_peers_configured_never_queries(self, monkeypatch):
        import ts_app.app as app_module

        def fail_urlopen(url, timeout):
            raise AssertionError("urlopen should not be called without peers")

        monkeypatch.setattr(app_module, "PEER_PORTS", [])
        monkeypatch.setattr(app_module, "urlopen", fail_urlopen)

        assert app_module.find_peer_session_with_file("/data/recording.npz") is None


class TestChooseFilePeerRefusal:
    def test_refuses_file_open_in_another_window(self, monkeypatch):
        import ts_app.app as app_module

        monkeypatch.setattr(app_module, "open_file_dialog", lambda file_types: "/data/recording.npz")
        monkeypatch.setattr(app_module, "find_peer_session_with_file", lambda filepath: 8061)
        initialize_state = MagicMock()
        monkeypatch.setattr(app_module, "initialize_state", initialize_state)

        message, ready = app_module.choose_file(1)

        assert '"recording.npz" is already open in another' in message
        assert ready is dash.no_update
        initialize_state.assert_not_called()

    def test_loads_file_when_no_peer_has_it(self, monkeypatch):
        import ts_app.app as app_module

        monkeypatch.setattr(app_module, "open_file_dialog", lambda file_types: "/data/recording.npz")
        monkeypatch.setattr(app_module, "find_peer_session_with_file", lambda filepath: None)
        initialize_state = MagicMock()
        monkeypatch.setattr(app_module, "initialize_state", initialize_state)

        message, ready = app_module.choose_file(1)

        assert ready == "vis"
        initialize_state.assert_called_once()
