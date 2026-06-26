from pathlib import Path


def test_documented_quality_commands_exist() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "python -m pytest" in readme
    assert "python -m ruff check ." in readme
