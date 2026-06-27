import paramiko

from remote_image_compare.domain.models import SftpAuthMode, SftpServerProfile
from remote_image_compare.services.remote_browser_service import RemoteBrowserService


def test_remote_browser_service_reports_successful_connection() -> None:
    events = []

    class FakeSftp:
        def listdir_attr(self, path):
            events.append(("listdir", path))
            return []

    class FakeClient:
        def __init__(self):
            self.connected = None

        def set_missing_host_key_policy(self, policy):
            events.append(("policy", type(policy).__name__))

        def connect(self, **kwargs):
            self.connected = kwargs
            events.append(("connect", kwargs["hostname"], kwargs["port"], kwargs["username"]))

        def open_sftp(self):
            return FakeSftp()

        def close(self):
            events.append(("close",))

    profile = SftpServerProfile(
        name="lab",
        host="127.0.0.1",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw",
        default_root="/srv/photos",
    )
    service = RemoteBrowserService(ssh_client_factory=FakeClient)

    ok, message = service.test_connection(profile)

    assert ok is True
    assert message == "连接成功"
    assert ("connect", "127.0.0.1", 2222, "tester") in events


def test_remote_browser_service_lists_only_child_directories() -> None:
    class Attr:
        def __init__(self, filename, mode):
            self.filename = filename
            self.st_mode = mode

    class FakeSftp:
        def listdir_attr(self, path):
            assert path == "/srv/photos"
            return [
                Attr("set_a", 0o040755),
                Attr("notes.txt", 0o100644),
                Attr("set_b", 0o040755),
            ]

    class FakeClient:
        def set_missing_host_key_policy(self, policy):
            del policy

        def connect(self, **kwargs):
            del kwargs

        def open_sftp(self):
            return FakeSftp()

        def close(self):
            return None

    profile = SftpServerProfile(
        name="lab",
        host="127.0.0.1",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw",
        default_root="/srv/photos",
    )
    service = RemoteBrowserService(ssh_client_factory=FakeClient)

    nodes = service.list_directories(profile, "/srv/photos")

    assert [node.path for node in nodes] == ["/srv/photos/set_a", "/srv/photos/set_b"]


def test_remote_browser_service_reports_authentication_failure() -> None:
    class FakeClient:
        def set_missing_host_key_policy(self, policy):
            del policy

        def connect(self, **kwargs):
            del kwargs
            raise Exception("bad password")

        def close(self):
            return None

    profile = SftpServerProfile(
        name="lab",
        host="127.0.0.1",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw",
        default_root="/srv/photos",
    )
    service = RemoteBrowserService(
        ssh_client_factory=FakeClient,
        authentication_error_types=(Exception,),
    )

    ok, message = service.test_connection(profile)

    assert ok is False
    assert message == "认证失败: bad password"


def test_remote_browser_service_retries_transient_banner_error() -> None:
    attempts = []

    class FakeSftp:
        def listdir_attr(self, path):
            assert path == "/srv/photos"
            return []

    class FakeClient:
        def set_missing_host_key_policy(self, policy):
            del policy

        def connect(self, **kwargs):
            del kwargs
            attempts.append("connect")
            if len(attempts) == 1:
                raise paramiko.SSHException("Error reading SSH protocol banner")

        def open_sftp(self):
            return FakeSftp()

        def close(self):
            return None

    profile = SftpServerProfile(
        name="lab",
        host="127.0.0.1",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw",
        default_root="/srv/photos",
    )
    service = RemoteBrowserService(ssh_client_factory=FakeClient)

    ok, message = service.test_connection(profile)

    assert ok is True
    assert message == "连接成功"
    assert attempts == ["connect", "connect"]


def test_remote_browser_service_reports_ssh_handshake_failure() -> None:
    class FakeClient:
        def set_missing_host_key_policy(self, policy):
            del policy

        def connect(self, **kwargs):
            del kwargs
            raise paramiko.SSHException("Error reading SSH protocol banner")

        def close(self):
            return None

    profile = SftpServerProfile(
        name="lab",
        host="127.0.0.1",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw",
        default_root="/srv/photos",
    )
    service = RemoteBrowserService(ssh_client_factory=FakeClient)

    ok, message = service.test_connection(profile)

    assert ok is False
    assert "SSH 握手失败: Error reading SSH protocol banner" in message
    assert "sudo systemctl enable --now ssh" in message


def test_remote_browser_service_reports_host_unreachable_with_detail() -> None:
    class FakeClient:
        def set_missing_host_key_policy(self, policy):
            del policy

        def connect(self, **kwargs):
            del kwargs
            raise OSError("Connection refused")

        def close(self):
            return None

    profile = SftpServerProfile(
        name="lab",
        host="127.0.0.1",
        port=2222,
        username="tester",
        auth_mode=SftpAuthMode.PASSWORD,
        password="pw",
        default_root="/srv/photos",
    )
    service = RemoteBrowserService(ssh_client_factory=FakeClient)

    ok, message = service.test_connection(profile)

    assert ok is False
    assert "主机不可达: Connection refused" in message
    assert "sudo systemctl enable --now ssh" in message
