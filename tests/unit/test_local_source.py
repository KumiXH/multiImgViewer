from pathlib import Path

from remote_image_compare.domain.models import SourceConfig, SourceKind
from remote_image_compare.sources.local_source import LocalPathSource


def test_local_source_lists_only_supported_images(tmp_path: Path) -> None:
    (tmp_path / "img2.jpg").write_bytes(b"jpg")
    (tmp_path / "img10.jpg").write_bytes(b"jpg")
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")

    source = LocalPathSource(
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        )
    )

    assert source.list_relative_paths() == ["img2.jpg", "img10.jpg"]


def test_local_source_reads_file_bytes(tmp_path: Path) -> None:
    image_path = tmp_path / "img1.jpg"
    image_path.write_bytes(b"image-data")

    source = LocalPathSource(
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=False,
        )
    )

    assert source.read_bytes("img1.jpg") == b"image-data"


def test_local_source_lists_nested_images_when_recursive_enabled(tmp_path: Path) -> None:
    nested = tmp_path / "setA"
    nested.mkdir()
    (nested / "img2.jpg").write_bytes(b"jpg")
    (nested / "notes.txt").write_text("ignore me", encoding="utf-8")

    source = LocalPathSource(
        SourceConfig(
            id="pane-1",
            kind=SourceKind.LOCAL,
            display_name="Local",
            root_path=str(tmp_path),
            recursive=True,
        )
    )

    assert source.list_relative_paths() == ["setA/img2.jpg"]
