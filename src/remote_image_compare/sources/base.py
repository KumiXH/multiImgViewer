from abc import ABC, abstractmethod


class ImageSource(ABC):
    @abstractmethod
    def list_relative_paths(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, relative_path: str) -> bytes:
        raise NotImplementedError
