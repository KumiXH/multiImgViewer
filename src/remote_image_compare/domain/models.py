from dataclasses import dataclass
from enum import Enum


class SourceKind(str, Enum):
    LOCAL = "local"
    UNC = "unc"
    SFTP = "sftp"


class CompareMode(str, Enum):
    COMMON = "common"
    PRIMARY = "primary"


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
