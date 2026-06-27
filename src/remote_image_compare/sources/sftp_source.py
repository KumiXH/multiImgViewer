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
    def __init__(self, config, auth, ssh_client_factory=None) -> None:
        self.config = config
        self.auth = auth
        self._ssh_client_factory = ssh_client_factory or paramiko.SSHClient
        self._client: paramiko.SSHClient | None = None
        self._sftp = None

    def connect(self, host: str, port: int, username: str) -> None:
        client = self._ssh_client_factory()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": username,
        }
        if self.auth.mode == "password":
            connect_kwargs["password"] = self.auth.password
        else:
            connect_kwargs["key_filename"] = self.auth.private_key_path
            if self.auth.passphrase:
                connect_kwargs["passphrase"] = self.auth.passphrase
        client.connect(**connect_kwargs)
        self._client = client
        self._sftp = client.open_sftp()

    def _ensure_sftp(self):
        if self._sftp is not None:
            return self._sftp
        raise RuntimeError("SFTP client not connected")

    def list_relative_paths(self) -> list[str]:
        client = self._ensure_sftp()
        results = self._list_relative_paths_recursive(client, self.config.root_path, "")
        return sorted(results, key=natural_key)

    def read_bytes(self, relative_path: str) -> bytes:
        client = self._ensure_sftp()
        remote_path = f"{self.config.root_path.rstrip('/')}/{relative_path}"
        with client.open(remote_path, "rb") as handle:
            return handle.read()

    def _list_relative_paths_recursive(
        self,
        client,
        current_path: str,
        relative_prefix: str,
    ) -> list[str]:
        results: list[str] = []
        for attr in client.listdir_attr(current_path):
            child_relative = f"{relative_prefix}/{attr.filename}" if relative_prefix else attr.filename
            child_path = f"{current_path.rstrip('/')}/{attr.filename}"
            if S_ISDIR(attr.st_mode):
                if self.config.recursive:
                    results.extend(
                        self._list_relative_paths_recursive(client, child_path, child_relative)
                    )
                continue
            suffix = "." + attr.filename.rsplit(".", 1)[-1].casefold() if "." in attr.filename else ""
            if suffix in IMAGE_SUFFIXES:
                results.append(child_relative)
        return results
