from remote_image_compare.domain.models import (
    SftpAuthConfig,
    SftpAuthMode,
    SourceConfig,
    SourceKind,
)
from remote_image_compare.sources.sftp_source import SftpSource


def test_sftp_auth_config_supports_password_mode() -> None:
    auth = SftpAuthConfig(mode=SftpAuthMode.PASSWORD, password="secret")
    assert auth.mode is SftpAuthMode.PASSWORD
    assert auth.password == "secret"


def test_sftp_auth_config_supports_key_mode() -> None:
    auth = SftpAuthConfig(
        mode=SftpAuthMode.KEY,
        private_key_path=r"C:\keys\id_ed25519",
        passphrase="pw",
    )
    assert auth.private_key_path.endswith("id_ed25519")


class FakeRemoteFile:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeSftpClient:
    def __init__(self) -> None:
        self.files = {
            "/photos/img2.jpg": b"two",
            "/photos/img10.jpg": b"ten",
        }

    def listdir_attr(self, path: str):
        class Attr:
            def __init__(self, filename: str) -> None:
                self.filename = filename
                self.st_mode = 0o100644

        return [Attr("img10.jpg"), Attr("img2.jpg"), Attr("notes.txt")]

    def open(self, path: str, mode: str):
        return FakeRemoteFile(self.files[path])


class FakeRecursiveSftpClient:
    def __init__(self) -> None:
        self.files = {
            "/photos/setA/img2.jpg": b"two",
            "/photos/setB/deeper/img10.jpg": b"ten",
        }
        self._entries = {
            "/photos": [
                ("setA", 0o040755),
                ("setB", 0o040755),
                ("notes.txt", 0o100644),
            ],
            "/photos/setA": [
                ("img2.jpg", 0o100644),
            ],
            "/photos/setB": [
                ("deeper", 0o040755),
            ],
            "/photos/setB/deeper": [
                ("img10.jpg", 0o100644),
            ],
        }

    def listdir_attr(self, path: str):
        class Attr:
            def __init__(self, filename: str, st_mode: int) -> None:
                self.filename = filename
                self.st_mode = st_mode

        return [Attr(name, mode) for name, mode in self._entries.get(path, [])]

    def open(self, path: str, mode: str):
        return FakeRemoteFile(self.files[path])


class FakeSshClient:
    def __init__(self) -> None:
        self.connect_kwargs = None
        self.sftp = FakeSftpClient()

    def set_missing_host_key_policy(self, policy) -> None:
        self.policy = policy

    def connect(self, **kwargs) -> None:
        self.connect_kwargs = kwargs

    def open_sftp(self):
        return self.sftp


def test_sftp_source_lists_supported_images() -> None:
    config = SourceConfig(
        id="pane-2",
        kind=SourceKind.SFTP,
        display_name="Remote",
        root_path="/photos",
        recursive=False,
    )
    source = SftpSource(config, auth=SftpAuthConfig(mode=SftpAuthMode.PASSWORD, password="pw"))
    source._sftp = FakeSftpClient()
    assert source.list_relative_paths() == ["img2.jpg", "img10.jpg"]


def test_sftp_source_reads_file_bytes() -> None:
    config = SourceConfig(
        id="pane-2",
        kind=SourceKind.SFTP,
        display_name="Remote",
        root_path="/photos",
        recursive=False,
    )
    source = SftpSource(config, auth=SftpAuthConfig(mode=SftpAuthMode.PASSWORD, password="pw"))
    source._sftp = FakeSftpClient()
    assert source.read_bytes("img2.jpg") == b"two"


def test_sftp_source_lists_nested_images_when_recursive_enabled() -> None:
    config = SourceConfig(
        id="pane-2",
        kind=SourceKind.SFTP,
        display_name="Remote",
        root_path="/photos",
        recursive=True,
    )
    source = SftpSource(config, auth=SftpAuthConfig(mode=SftpAuthMode.PASSWORD, password="pw"))
    source._sftp = FakeRecursiveSftpClient()

    assert source.list_relative_paths() == ["setA/img2.jpg", "setB/deeper/img10.jpg"]


def test_sftp_source_connects_with_password_auth() -> None:
    config = SourceConfig(
        id="pane-2",
        kind=SourceKind.SFTP,
        display_name="Remote",
        root_path="/photos",
        recursive=False,
    )
    client = FakeSshClient()
    source = SftpSource(
        config,
        auth=SftpAuthConfig(mode=SftpAuthMode.PASSWORD, password="pw"),
        ssh_client_factory=lambda: client,
    )

    source.connect(host="127.0.0.1", port=22, username="tester")

    assert client.connect_kwargs is not None
    assert client.connect_kwargs["hostname"] == "127.0.0.1"
    assert client.connect_kwargs["password"] == "pw"
