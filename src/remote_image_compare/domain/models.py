from dataclasses import dataclass
from enum import Enum


class SourceKind(str, Enum):
    LOCAL = "local"
    UNC = "unc"
    SFTP = "sftp"


class CompareMode(str, Enum):
    COMMON = "common"
    PRIMARY = "primary"


@dataclass(frozen=True)
class SourceConfig:
    id: str
    kind: SourceKind
    display_name: str
    root_path: str
    recursive: bool = False
