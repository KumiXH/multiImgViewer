from dataclasses import dataclass
from enum import Enum


class SourceKind(str, Enum):
    LOCAL = "local"
    UNC = "unc"
    SFTP = "sftp"


class CompareMode(str, Enum):
    COMMON = "common"
    PRIMARY = "primary"


class ToleranceAlgorithm(str, Enum):
    MAX_CHANNEL = "max_channel"
    AVERAGE = "average"
    EUCLIDEAN = "euclidean"


class SftpAuthMode(str, Enum):
    PASSWORD = "password"
    KEY = "key"


@dataclass(frozen=True)
class SourceConfig:
    id: str
    kind: SourceKind
    display_name: str
    root_path: str
    recursive: bool = False


@dataclass(frozen=True)
class SftpAuthConfig:
    mode: SftpAuthMode
    password: str | None = None
    private_key_path: str | None = None
    passphrase: str | None = None


@dataclass(frozen=True)
class SftpConnectionConfig:
    host: str
    port: int
    username: str


@dataclass(frozen=True)
class SftpServerProfile:
    name: str
    host: str
    port: int
    username: str
    auth_mode: SftpAuthMode
    password: str = ""
    private_key_path: str | None = None
    passphrase: str = ""
    default_root: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.auth_mode, SftpAuthMode):
            object.__setattr__(self, "auth_mode", SftpAuthMode(self.auth_mode))

    def to_auth_config(self) -> SftpAuthConfig:
        return SftpAuthConfig(
            mode=self.auth_mode,
            password=self.password or None,
            private_key_path=self.private_key_path,
            passphrase=self.passphrase or None,
        )

    def to_connection_config(self) -> SftpConnectionConfig:
        return SftpConnectionConfig(
            host=self.host,
            port=self.port,
            username=self.username,
        )


@dataclass(frozen=True)
class SessionPaneBinding:
    pane_index: int
    source_kind: SourceKind
    display_name: str
    root_path: str | None = None
    server_name: str | None = None
    remote_path: str | None = None


@dataclass(frozen=True)
class SessionRecord:
    id: str
    name: str
    saved_at: str
    layout_mode: str
    compare_mode: CompareMode
    panes: tuple[SessionPaneBinding, ...]
