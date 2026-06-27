from remote_image_compare.services import runtime_paths
from remote_image_compare.services.server_profile_store import default_profile_store_path
from remote_image_compare.services.session_record_store import default_session_record_store_path
from remote_image_compare.services.window_state_store import default_window_state_store_path


def test_application_root_defaults_to_repo_root_in_dev_mode() -> None:
    root = runtime_paths.application_root()

    assert (root / "pyproject.toml").exists()


def test_app_data_dir_lives_under_application_root() -> None:
    app_root = runtime_paths.application_root()

    assert runtime_paths.app_data_dir() == app_root / ".remote_image_compare"


def test_store_paths_use_shared_app_data_dir() -> None:
    data_dir = runtime_paths.app_data_dir()

    assert default_profile_store_path() == data_dir / "server_profiles.json"
    assert default_session_record_store_path() == data_dir / "session_records.json"
    assert default_window_state_store_path() == data_dir / "window_state.json"
