from importlib import import_module


def test_package_exposes_version() -> None:
    package = import_module("remote_image_compare")
    assert package.__version__ == "0.1.0"
