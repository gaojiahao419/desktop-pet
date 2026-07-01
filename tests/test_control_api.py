import json
import urllib.request

from control_api import ControlApiSignals, ControlApiServer, ControlApiStateStore


class SignalRecorder:
    def __init__(self) -> None:
        self.calls = []

    def emit(self, *args) -> None:
        self.calls.append(args)


class FakeSignals:
    def __init__(self) -> None:
        for name in ControlApiSignals.signal_names():
            setattr(self, name, SignalRecorder())


def read_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict = None) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def test_control_api_state_store_matches_web_control_payload():
    store = ControlApiStateStore()

    snapshot = store.snapshot()

    assert list(snapshot["states"]) == ["idle", "happy", "angry", "sleep"]
    assert snapshot["states"]["sleep"]["title"] == "睡觉动作"
    assert snapshot["actions"][-1]["state"] == "show"
    assert snapshot["blackBackground"] is False
    assert snapshot["preview"]["frameLabel"] == "当前帧：0 / 0"
    assert snapshot["revision"] == store.snapshot()["revision"]


def test_control_api_state_store_revisions_change_only_after_updates():
    store = ControlApiStateStore()
    first_revision = store.snapshot()["revision"]

    assert store.snapshot()["revision"] == first_revision

    store.set_state_scale_percent("happy", 130)

    assert store.snapshot()["revision"] > first_revision


def test_control_api_serves_and_updates_state_over_http():
    store = ControlApiStateStore()
    signals = FakeSignals()
    server = ControlApiServer(store, signals)
    server.start()
    try:
        assert read_json(f"{server.url}/api/state")["status"] == "状态：使用内置绘制宠物"

        payload = post_json(f"{server.url}/api/state-scale", {"state": "happy", "percent": 125})
        assert payload["states"]["happy"]["scalePercent"] == 125
        assert signals.state_scale_requested.calls == [("happy", 1.25)]

        payload = post_json(f"{server.url}/api/state-speed", {"state": "happy", "percent": 150})
        assert payload["states"]["happy"]["speedPercent"] == 150
        assert signals.state_playback_speed_requested.calls == [("happy", 1.5)]
    finally:
        server.stop()


def test_control_api_accepts_selected_video_path_from_electron():
    store = ControlApiStateStore()
    signals = FakeSignals()
    server = ControlApiServer(store, signals)
    server.start()
    try:
        payload = post_json(
            f"{server.url}/api/state-video",
            {"state": "idle", "path": "D:/pet/idle.mp4"},
        )

        assert payload["states"]["idle"]["materialName"] == "idle.mp4"
        assert payload["states"]["idle"]["status"] == "加载中：正在解析素材"
        assert signals.state_video_requested.calls == [("idle", "D:/pet/idle.mp4", False)]
    finally:
        server.stop()
