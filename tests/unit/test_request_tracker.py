from remote_image_compare.services.image_loader import RequestTracker


def test_request_tracker_accepts_only_latest_token() -> None:
    tracker = RequestTracker()
    first = tracker.next_token("pane-1")
    second = tracker.next_token("pane-1")

    assert first != second
    assert tracker.is_current("pane-1", second) is True
    assert tracker.is_current("pane-1", first) is False
