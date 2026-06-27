from pathlib import Path

import tomllib


def test_main_window_title_uses_project_name() -> None:
    source = Path("src/remote_image_compare/ui/main_window.py").read_text(encoding="utf-8")

    assert 'setWindowTitle("mulitImgViewer")' in source


def test_pyinstaller_release_uses_project_name() -> None:
    spec = Path("mulitImgViewer.spec").read_text(encoding="utf-8")
    build_script = Path("tools/build_release.ps1").read_text(encoding="utf-8")

    assert 'name="mulitImgViewer"' in spec
    assert "mulitImgViewer.spec" in build_script
    assert 'dist\\mulitImgViewer' in build_script
    assert "RemoteImageCompare" not in spec
    assert "RemoteImageCompare" not in build_script


def test_project_metadata_uses_project_name() -> None:
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["name"] == "mulitImgViewer"
    assert "mulitImgViewer" in metadata["project"]["scripts"]


def test_readme_uses_project_name_for_download_and_exe() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "mulitImgViewer-V1.0-windows-x64.zip" in readme
    assert "mulitImgViewer.exe" in readme
    assert "dist\\mulitImgViewer\\mulitImgViewer.exe" in readme
    assert "multiImgViewer" not in readme
    assert "RemoteImageCompare" not in readme
