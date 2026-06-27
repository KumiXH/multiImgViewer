from pathlib import Path

from remote_image_compare.services.window_state_store import WindowStateStore


def test_window_state_store_round_trips_window_sizes(tmp_path: Path) -> None:
    store = WindowStateStore(tmp_path / "window_state.json")

    store.save_window_size("main_window", 1200, 800)
    store.save_window_size("tolerance_window", 640, 420)
    store.save_window_position("main_window", 120, 80)
    store.save_window_position("tolerance_window", 240, 160)

    reloaded = WindowStateStore(tmp_path / "window_state.json")
    assert reloaded.load_window_size("main_window") == (1200, 800)
    assert reloaded.load_window_size("tolerance_window") == (640, 420)
    assert reloaded.load_window_position("main_window") == (120, 80)
    assert reloaded.load_window_position("tolerance_window") == (240, 160)


def test_window_state_store_returns_none_for_missing_window(tmp_path: Path) -> None:
    store = WindowStateStore(tmp_path / "window_state.json")

    assert store.load_window_size("main_window") is None
    assert store.load_window_position("main_window") is None
