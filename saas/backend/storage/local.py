from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO


class LocalStorage:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def path_for_key(self, key: str) -> Path:
        p = PurePosixPath(key)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("Invalid storage key")
        return (self.root_dir / Path(*p.parts)).resolve()

    def write_bytes(self, key: str, data: bytes) -> str:
        path = self.path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def write_json(self, key: str, obj: Any) -> str:
        data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        return self.write_bytes(key, data)

    def read_bytes(self, key: str) -> bytes:
        return self.path_for_key(key).read_bytes()

    def open(self, key: str) -> BinaryIO:
        return self.path_for_key(key).open("rb")

    def exists(self, key: str) -> bool:
        return self.path_for_key(key).exists()
