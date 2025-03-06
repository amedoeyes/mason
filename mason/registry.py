import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any

import requests

from mason import config
from mason.utility import download_file, extract_file


def _verify_checksums(checksums_file: Path) -> bool:
    for line in checksums_file.read_text().splitlines():
        expected_hash, file = line.split()
        file_path = checksums_file.parent / file
        if not file_path.exists() or hashlib.sha256(file_path.read_bytes()).hexdigest() != expected_hash:
            return False
    return True


def _download_assets(data: Any):
    registry_dir = config.registries_dir / "github" / config.registry_repo
    registry_dir.mkdir(parents=True, exist_ok=True)
    checksums_txt = registry_dir / "checksums.txt"
    registry_json_zip = registry_dir / "registry.json.zip"
    info_json = registry_dir / "info.json"

    assets = {asset["name"]: asset["browser_download_url"] for asset in data["assets"]}

    download_file(assets["checksums.txt"], checksums_txt)
    download_file(assets["registry.json.zip"], registry_json_zip)
    extract_file(registry_json_zip, registry_dir)
    _verify_checksums(checksums_txt)

    info_json.write_text(
        json.dumps(
            {
                "download_timestamp": int(time.time()),
                "version": data["tag_name"],
                "checksums": {p[1]: p[0] for l in checksums_txt.read_text().splitlines() if (p := l.split())},
            },
            indent=2,
        )
    )

    os.remove(registry_json_zip)
    os.remove(checksums_txt)

    print("Registry downloaded")


def download() -> None:
    print("Downloading registry...")
    response = requests.get(f"https://api.github.com/repos/{config.registry_repo}/releases/latest")
    response.raise_for_status()
    _download_assets(response.json())


def update() -> None:
    print("Checking for update...")
    response = requests.get(f"https://api.github.com/repos/{config.registry_repo}/releases/latest")
    response.raise_for_status()
    data = response.json()
    info = json.loads((config.registries_dir / "github" / config.registry_repo / "info.json").read_text())
    if data["tag_name"] == info["version"]:
        print("Registry up-to-date")
        return
    _download_assets(response.json())
