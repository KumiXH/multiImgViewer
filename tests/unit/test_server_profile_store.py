from pathlib import Path

from remote_image_compare.domain.models import SftpAuthMode, SftpServerProfile
from remote_image_compare.services.server_profile_store import ServerProfileStore


def test_server_profile_store_round_trips_profiles(tmp_path: Path) -> None:
    store = ServerProfileStore(tmp_path / "profiles.json")
    profile = SftpServerProfile(
        name="lab",
        host="192.168.1.9",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.KEY,
        password="",
        private_key_path=r"C:\keys\id_ed25519",
        passphrase="secret",
        default_root="/srv/photos",
    )

    store.save_profile(profile)

    reloaded = ServerProfileStore(tmp_path / "profiles.json").list_profiles()
    assert reloaded == [profile]


def test_server_profile_store_replaces_profile_with_same_name(tmp_path: Path) -> None:
    store = ServerProfileStore(tmp_path / "profiles.json")
    store.save_profile(
        SftpServerProfile(
            name="lab",
            host="192.168.1.9",
            port=22,
            username="tester",
            auth_mode=SftpAuthMode.PASSWORD,
            password="old",
            private_key_path=None,
            passphrase="",
            default_root="/srv/photos",
        )
    )

    replacement = SftpServerProfile(
        name="lab",
        host="192.168.1.10",
        port=2200,
        username="tester2",
        auth_mode=SftpAuthMode.PASSWORD,
        password="new",
        private_key_path=None,
        passphrase="",
        default_root="/mnt/data",
    )
    store.save_profile(replacement)

    assert store.list_profiles() == [replacement]


def test_server_profile_accepts_string_auth_mode_from_ui(tmp_path: Path) -> None:
    store = ServerProfileStore(tmp_path / "profiles.json")
    profile = SftpServerProfile(
        name="ui-profile",
        host="127.0.0.1",
        port=2222,
        username="tester",
        auth_mode="password",
        password="pw",
        private_key_path=None,
        passphrase="",
        default_root="/srv/photos",
    )

    store.save_profile(profile)

    loaded = store.list_profiles()
    assert loaded[0].auth_mode == SftpAuthMode.PASSWORD
