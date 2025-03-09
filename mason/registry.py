from dataclasses import dataclass
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import requests
import yaml

from mason import config
from mason.utility import download_github_release, extract_file


def _verify_checksums(checksums_file: Path) -> bool:
    for line in checksums_file.read_text().splitlines():
        expected_hash, file = line.split()
        file_path = checksums_file.parent / file
        if not file_path.exists() or hashlib.sha256(file_path.read_bytes()).hexdigest() != expected_hash:
            return False
    return True


@dataclass
class Registry:
    type: str
    source: str
    path: Path
    packages: list[dict[str, Any]]
    info: dict[str, Any]

    def __init__(self, registry: str) -> None:
        self.type, self.source = registry.split(":", 1)
        self._load()

    def update(self) -> None:
        match self.type:
            case "github":
                response = requests.get(f"https://api.github.com/repos/{config.registry_repo}/releases/latest")
                response.raise_for_status()
                data = response.json()
                if data["tag_name"] != self.info["version"]:
                    self._download_github_registry()
                    self._load()
            case "file":
                pass
            case _:
                raise Exception(f"Registry type '{self.type}' not implemented")

    def _download_github_registry(self) -> None:
        download_github_release(self.source, "registry.json.zip", out_path=self.path)
        extract_file(self.path / "registry.json.zip", self.path)
        download_github_release(self.source, "checksums.txt", out_path=self.path)
        _verify_checksums(self.path / "checksums.txt")
        response = requests.get(f"https://api.github.com/repos/{self.source}/releases/latest")
        response.raise_for_status()
        data = response.json()
        self.info = {
            "download_timestamp": int(time.time()),
            "version": data["tag_name"],
            "checksums": {
                p[1]: p[0] for l in (self.path / "checksums.txt").read_text().splitlines() if (p := l.split())
            },
        }
        (self.path / "info.json").write_text(json.dumps(self.info, indent=2))
        os.remove(self.path / "registry.json.zip")
        os.remove(self.path / "checksums.txt")

    def _load(self) -> None:
        match self.type:
            case "github":
                self.path = config.registries_dir / "github" / self.source
                if not (self.path / "info.json").exists() or not (self.path / "registry.json").exists():
                    self.path.mkdir(parents=True, exist_ok=True)
                    self._download_github_registry()
                self.packages = json.loads((self.path / "registry.json").read_bytes())
                self.info = json.loads((self.path / "info.json").read_bytes())
            case "file":
                self.path = Path(self.source)
                self.packages = list(
                    yaml.load_all(
                        b"".join((file / "package.yaml").read_bytes() for file in (self.path / "packages").iterdir()),
                        yaml.CSafeLoader,
                    )
                )
            case _:
                raise Exception(f"Registry type '{self.type}' not implemented")
