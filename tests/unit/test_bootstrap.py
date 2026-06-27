from pathlib import Path

from remote_image_compare.bootstrap import configure_frozen_windows_dll_paths


def test_configure_frozen_windows_dll_paths_registers_qt_package_dirs_only(tmp_path: Path) -> None:
    base_dir = tmp_path / "_internal"
    pyside_dir = base_dir / "PySide6"
    shiboken_dir = base_dir / "shiboken6"
    pyside_dir.mkdir(parents=True)
    shiboken_dir.mkdir(parents=True)
    (base_dir / "icuuc.dll").write_text("conflicting dll")

    seen_dirs: list[str] = []
    env = {"PATH": "C:\\Windows\\System32"}

    configured = configure_frozen_windows_dll_paths(
        base_dir=base_dir,
        is_windows=True,
        add_dll_directory=seen_dirs.append,
        environment=env,
    )

    assert configured == [pyside_dir, shiboken_dir]
    assert seen_dirs == [str(pyside_dir), str(shiboken_dir)]
    assert env["PATH"].startswith(f"{pyside_dir};{shiboken_dir};")


def test_configure_frozen_windows_dll_paths_is_noop_on_non_windows(tmp_path: Path) -> None:
    env = {"PATH": "/usr/bin"}

    configured = configure_frozen_windows_dll_paths(
        base_dir=tmp_path,
        is_windows=False,
        add_dll_directory=lambda path: (_ for _ in ()).throw(AssertionError(path)),
        environment=env,
    )

    assert configured == []
    assert env["PATH"] == "/usr/bin"
