import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app


def test_index_renders_dashboard():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert "Server Monitor" in response.get_data(as_text=True)


def test_stats_api_returns_expected_sections():
    client = app.test_client()

    response = client.get("/api/stats")
    data = response.get_json()

    assert response.status_code == 200
    assert {"cpu", "memory", "swap", "disk", "network", "system", "timestamp"} <= data.keys()
    assert isinstance(data["cpu"]["percent"], (int, float))
    assert isinstance(data["memory"]["percent"], (int, float))
    assert "hostname" in data["system"]


def test_processes_api_returns_process_list():
    client = app.test_client()

    response = client.get("/api/processes")
    data = response.get_json()

    assert response.status_code == 200
    assert isinstance(data, list)
    if data:
        assert {"pid", "name", "cpu_percent", "memory_percent", "username"} <= data[0].keys()
