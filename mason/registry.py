import hashlib
from pathlib import Path

import mason.config as config
from mason.downloaders import download_github_release
from mason.utility import extract_file


def _verify_checksums(checksum_file: Path) -> bool:
    for line in checksum_file.read_text():
        expected_hash, file = line.split()
        file_path = checksum_file.parent / file
        if not file_path.exists() or hashlib.sha256(file_path.read_bytes()).hexdigest() != expected_hash:
            return False
    return True


def download_registry() -> None:
    checksums_file = config.cache_dir / "checksums.txt"
    if checksums_file.exists():
        print("Checking for update...")
    download_github_release(config.registry_repo, "checksums.txt", "latest", config.cache_dir)
    if _verify_checksums(checksums_file):
        print("Registry up-to-date")
        return
    print("Downloading registry..." if not config.registry_path.exists() else "Updating registry...")
    download_github_release(config.registry_repo, "registry.json.zip", "latest", config.cache_dir)
    extract_file(config.cache_dir / "registry.json.zip", config.cache_dir)
