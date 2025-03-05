import hashlib
from pathlib import Path

from mason import config
from mason.utility import download_github_release, extract_file

_checksums_file = config.cache_dir / "checksums.txt"


def _verify_checksums(checksum_file: Path) -> bool:
    for line in checksum_file.read_text().splitlines():
        expected_hash, file = line.split()
        file_path = checksum_file.parent / file
        if not file_path.exists() or hashlib.sha256(file_path.read_bytes()).hexdigest() != expected_hash:
            return False
    return True


def download() -> None:
    print("Downloading registry...")
    download_github_release(config.registry_repo, "checksums.txt", out_path=config.cache_dir)
    download_github_release(config.registry_repo, "registry.json.zip", out_path=config.cache_dir)
    extract_file(config.cache_dir / "registry.json.zip", config.cache_dir)


def update() -> None:
    print("Checking for update...")
    download_github_release(config.registry_repo, "checksums.txt", out_path=config.cache_dir)
    if _verify_checksums(_checksums_file):
        print("Registry up-to-date")
        return
    print("Updating registry...")
    download_github_release(config.registry_repo, "registry.json.zip", out_path=config.cache_dir)
    extract_file(config.cache_dir / "registry.json.zip", config.cache_dir)
