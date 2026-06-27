from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from remote_image_compare.domain.models import SftpAuthMode, SftpServerProfile
from remote_image_compare.services.runtime_paths import app_data_dir


def default_profile_store_path() -> Path:
    return app_data_dir() / "server_profiles.json"


class ServerProfileStore:
    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = Path(storage_path) if storage_path is not None else default_profile_store_path()

    def list_profiles(self) -> list[SftpServerProfile]:
        if not self.storage_path.exists():
            return []
        payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        return [self._deserialize_profile(item) for item in payload.get("profiles", [])]

    def save_profile(self, profile: SftpServerProfile) -> None:
        profiles = [item for item in self.list_profiles() if item.name != profile.name]
        profiles.append(profile)
        self._write_profiles(profiles)

    def delete_profile(self, profile_name: str) -> None:
        profiles = [item for item in self.list_profiles() if item.name != profile_name]
        self._write_profiles(profiles)

    def _write_profiles(self, profiles: list[SftpServerProfile]) -> None:
        payload = {
            "profiles": [
                {
                    **asdict(profile),
                    "auth_mode": profile.auth_mode.value,
                }
                for profile in sorted(profiles, key=lambda item: item.name.casefold())
            ]
        }
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _deserialize_profile(self, payload: dict) -> SftpServerProfile:
        return SftpServerProfile(
            name=payload["name"],
            host=payload["host"],
            port=int(payload["port"]),
            username=payload["username"],
            auth_mode=SftpAuthMode(payload["auth_mode"]),
            password=payload.get("password", ""),
            private_key_path=payload.get("private_key_path"),
            passphrase=payload.get("passphrase", ""),
            default_root=payload.get("default_root", ""),
        )
