from remote_image_compare.domain.models import CompareMode
from remote_image_compare.services.catalog import build_catalog


def test_build_catalog_returns_intersection_for_common_mode() -> None:
    entries = {
        "pane-a": {"img1.jpg", "img2.jpg", "img10.jpg"},
        "pane-b": {"img2.jpg", "img10.jpg", "img20.jpg"},
    }
    assert build_catalog(entries, CompareMode.COMMON) == ["img2.jpg", "img10.jpg"]


def test_build_catalog_uses_first_pane_for_primary_mode() -> None:
    entries = {
        "pane-a": {"img2.jpg", "img10.jpg", "img1.jpg"},
        "pane-b": {"img10.jpg"},
    }
    assert build_catalog(entries, CompareMode.PRIMARY) == ["img1.jpg", "img2.jpg", "img10.jpg"]
