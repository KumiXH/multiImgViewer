from stat import S_ISDIR

import paramiko

from remote_image_compare.domain.sorting import natural_key
from remote_image_compare.sources.base import ImageSource

IMAGE_SUFFIXES = {
    ".bmp",
    ".dib",
    ".gif",
    ".jfif",
    ".jpe",
    ".jpeg",
    ".jpg",
    ".pbm",
    ".pgm",
    ".png",
    ".ppm",
    ".tif",
    ".tiff",
    ".webp",
}


class SftpSource(ImageSource):
    def __init__(self, config, auth) -> None:
        self.config = config
        self.auth = auth
        self._client: paramiko.SSHClient | None = None
        self._sftp = None

    def _ensure_sftp(self):
        if self._sftp is not None:
            return self._sftp
        raise RuntimeError("SFTP client not connected")

    def list_relative_paths(self) -> list[str]:
        client = self._ensure_sftp()
        results: list[str] = []
        for attr in client.listdir_attr(self.config.root_path):
            if S_ISDIR(attr.st_mode):
                continue
            filename = attr.filename
            suffix = "." + filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
            if suffix in IMAGE_SUFFIXES:
                results.append(filename)
        return sorted(results, key=natural_key)

    def read_bytes(self, relative_path: str) -> bytes:
        client = self._ensure_sftp()
        remote_path = f"{self.config.root_path.rstrip('/')}/{relative_path}"
        with client.open(remote_path, "rb") as handle:
            return handle.read()
