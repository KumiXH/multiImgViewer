from remote_image_compare.domain.models import CompareMode, SourceConfig, SourceKind
from remote_image_compare.domain.sorting import natural_key


def test_natural_key_orders_numeric_suffixes() -> None:
    names = ["img10.jpg", "img2.jpg", "img1.jpg"]
    assert sorted(names, key=natural_key) == ["img1.jpg", "img2.jpg", "img10.jpg"]


def test_source_config_exposes_display_name() -> None:
    config = SourceConfig(
        id="pane-1",
        kind=SourceKind.LOCAL,
        display_name="Local Set",
        root_path=r"D:\photos",
        recursive=False,
    )
    assert config.display_name == "Local Set"
    assert CompareMode.COMMON.value == "common"
