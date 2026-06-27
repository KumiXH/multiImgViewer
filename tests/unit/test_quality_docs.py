from pathlib import Path


def test_documented_quality_commands_exist() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "python -m pytest" in readme
    assert "python -m ruff check ." in readme


def test_readme_documents_local_dataset_run_command() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert ".\\tools\\run_local_dataset.ps1" in readme
    assert "D:\\SR数据集\\livePhoto_out\\HR" in readme
