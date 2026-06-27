from __future__ import annotations

from dataclasses import dataclass
from stat import S_ISDIR
from time import sleep

import paramiko

from remote_image_compare.domain.models import SftpAuthMode, SftpServerProfile


@dataclass(frozen=True)
class RemoteDirectoryNode:
    name: str
    path: str
    has_children: bool = True


class RemoteBrowserService:
    def __init__(
        self,
        ssh_client_factory=None,
        authentication_error_types: tuple[type[BaseException], ...] | None = None,
        handshake_retry_attempts: int = 2,
        handshake_retry_delay_seconds: float = 0.2,
    ) -> None:
        self._ssh_client_factory = ssh_client_factory or paramiko.SSHClient
        self._authentication_error_types = authentication_error_types or (
            paramiko.AuthenticationException,
        )
        self._handshake_retry_attempts = max(1, handshake_retry_attempts)
        self._handshake_retry_delay_seconds = max(0.0, handshake_retry_delay_seconds)

    def test_connection(self, profile: SftpServerProfile) -> tuple[bool, str]:
        client = None
        try:
            client = self._connect(profile)
            sftp = client.open_sftp()
            if sftp is not None:
                sftp.listdir_attr(profile.default_root or "/")
            return True, "\u8fde\u63a5\u6210\u529f"
        except self._authentication_error_types as exc:
            return False, self._format_error_message(
                "\u8ba4\u8bc1\u5931\u8d25",
                exc,
                profile,
            )
        except TimeoutError as exc:
            return False, self._format_error_message(
                "\u8fde\u63a5\u8d85\u65f6",
                exc,
                profile,
            )
        except paramiko.SSHException as exc:
            return False, self._format_error_message(
                "SSH \u63e1\u624b\u5931\u8d25",
                exc,
                profile,
            )
        except OSError as exc:
            return False, self._format_error_message(
                "\u4e3b\u673a\u4e0d\u53ef\u8fbe",
                exc,
                profile,
            )
        except Exception as exc:
            return False, self._format_error_message(
                "SFTP \u521d\u59cb\u5316\u5931\u8d25",
                exc,
                profile,
            )
        finally:
            if client is not None:
                self._close_quietly(client)

    def list_directories(
        self, profile: SftpServerProfile, remote_path: str
    ) -> list[RemoteDirectoryNode]:
        client = None
        try:
            client = self._connect(profile)
            sftp = client.open_sftp()
            nodes: list[RemoteDirectoryNode] = []
            for attr in sftp.listdir_attr(remote_path):
                if not S_ISDIR(attr.st_mode):
                    continue
                if remote_path == "/":
                    child_path = f"/{attr.filename}"
                else:
                    child_path = f"{remote_path.rstrip('/')}/{attr.filename}"
                nodes.append(RemoteDirectoryNode(name=attr.filename, path=child_path))
            return sorted(nodes, key=lambda node: node.name.casefold())
        finally:
            if client is not None:
                self._close_quietly(client)

    def _connect(self, profile: SftpServerProfile):
        last_error = None
        for attempt in range(self._handshake_retry_attempts):
            client = self._ssh_client_factory()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(**self._build_connect_kwargs(profile))
                return client
            except paramiko.SSHException as exc:
                self._close_quietly(client)
                last_error = exc
                if not self._is_retryable_handshake_error(exc):
                    raise
                if attempt + 1 >= self._handshake_retry_attempts:
                    raise
                if self._handshake_retry_delay_seconds > 0:
                    sleep(self._handshake_retry_delay_seconds)
            except Exception:
                self._close_quietly(client)
                raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("SSH connection attempt did not start")

    def _build_connect_kwargs(self, profile: SftpServerProfile) -> dict[str, object]:
        connect_kwargs: dict[str, object] = {
            "hostname": profile.host,
            "port": profile.port,
            "username": profile.username,
            "timeout": 10,
            "banner_timeout": 10,
            "auth_timeout": 10,
        }
        if profile.auth_mode == SftpAuthMode.PASSWORD:
            connect_kwargs["password"] = profile.password
        else:
            connect_kwargs["key_filename"] = profile.private_key_path
            if profile.passphrase:
                connect_kwargs["passphrase"] = profile.passphrase
        return connect_kwargs

    def _is_retryable_handshake_error(self, error: paramiko.SSHException) -> bool:
        return "error reading ssh protocol banner" in str(error).casefold()

    def _format_error_message(
        self,
        title: str,
        error: BaseException,
        profile: SftpServerProfile,
    ) -> str:
        details = self._summarize_error(error)
        message = title if not details else f"{title}: {details}"
        hint = self._wsl_hint_for_error(title, profile)
        if hint:
            return f"{message}\n{hint}"
        return message

    def _summarize_error(self, error: BaseException) -> str:
        text = str(error).strip()
        if text:
            return text
        return type(error).__name__

    def _wsl_hint_for_error(self, title: str, profile: SftpServerProfile) -> str:
        if title not in {"SSH \u63e1\u624b\u5931\u8d25", "\u4e3b\u673a\u4e0d\u53ef\u8fbe"}:
            return ""
        if profile.host not in {"127.0.0.1", "localhost", "::1"}:
            return ""
        return (
            "WSL \u63d0\u793a\uff1a\u5982\u679c\u8fd9\u662f WSL \u672c\u673a\u8fde\u63a5\uff0c"
            "\u8bf7\u5148\u5728 WSL \u5185\u6267\u884c `sudo systemctl enable --now ssh`\u3002"
        )

    def _close_quietly(self, client) -> None:
        try:
            client.close()
        except Exception:
            pass
