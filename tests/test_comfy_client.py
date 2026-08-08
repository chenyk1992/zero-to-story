"""Unit tests for ComfyApiClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from lfo.comfy.client import ComfyApiClient
from lfo.comfy.exceptions import ComfyUnreachableError

# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def client():
    return ComfyApiClient("http://127.0.0.1:8188")


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError("error")
    else:
        resp.raise_for_status.return_value = None
    return resp


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


class TestComfyApiClient:
    def test_init_default_url(self):
        c = ComfyApiClient()
        assert c.base_url == "http://127.0.0.1:8188"

    def test_init_custom_url(self):
        c = ComfyApiClient("http://10.0.0.1:9999")
        assert c.base_url == "http://10.0.0.1:9999"

    def test_url_construction(self, client):
        assert client._url("/system_stats") == "http://127.0.0.1:8188/system_stats"

    def test_get_system_stats(self, client):
        with patch.object(client, "_request", return_value=_mock_response({"devices": []})):
            result = client.get_system_stats()
            assert result == {"devices": []}

    def test_get_features(self, client):
        with patch.object(client, "_request", return_value=_mock_response({"feature_x": True})):
            result = client.get_features()
            assert result["feature_x"] is True

    def test_get_object_info_no_arg(self, client):
        with patch.object(client, "_request", return_value=_mock_response({"NodeA": {}})):
            result = client.get_object_info()
            assert "NodeA" in result

    def test_get_object_info_with_class(self, client):
        with patch.object(client, "_request", return_value=_mock_response({"MiniMaxH3ImageToVideo": {}})):
            result = client.get_object_info("MiniMaxH3ImageToVideo")
            assert "MiniMaxH3ImageToVideo" in result

    def test_get_queue(self, client):
        data = {"queue_running": [], "queue_pending": []}
        with patch.object(client, "_request", return_value=_mock_response(data)):
            result = client.get_queue()
            assert result["queue_running"] == []

    def test_submit_prompt(self, client):
        data = {"prompt_id": "abc-123", "node_id": "5", "type": "SaveVideo"}
        with patch.object(client, "_request", return_value=_mock_response(data)):
            result = client.submit_prompt({"1": {}}, "client-1")
            assert result["prompt_id"] == "abc-123"

    def test_get_history(self, client):
        data = {"prompt-1": {"status": {"completed": True}}}
        with patch.object(client, "_request", return_value=_mock_response(data)):
            result = client.get_history("prompt-1")
            assert result["prompt-1"]["status"]["completed"] is True

    def test_interrupt(self, client):
        with patch.object(client, "_request", return_value=MagicMock()):
            client.interrupt()  # should not raise

    def test_unreachable_raises(self, client):
        with patch.object(
            client._session,
            "request",
            side_effect=requests.ConnectionError("refused"),
        ):
            with pytest.raises(ComfyUnreachableError):
                client.get_system_stats()

    def test_timeout_raises(self, client):
        with patch.object(
            client._session,
            "request",
            side_effect=requests.Timeout("timed out"),
        ):
            with pytest.raises(ComfyUnreachableError):
                client.get_system_stats()
