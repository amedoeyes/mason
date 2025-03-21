from functools import lru_cache
import gzip
import os
from pathlib import Path
import platform
import shutil
import tarfile
from typing import Any, Optional
import zipfile

import requests
from tqdm import tqdm


def extract_file(file_path: Path, out_path=Path(".")) -> None:
    match file_path.suffixes[-2:]:
        case [".tar", ".gz"] | [_, ".tgz"] | [".tgz"]:
            with tarfile.open(file_path, "r:gz") as tar:
                tar.extractall(path=out_path, filter="data")
        case [".tar", ".bz2"] | [_, ".tbz2"] | [".tbz2"]:
            with tarfile.open(file_path, "r:bz2") as tar:
                tar.extractall(path=out_path, filter="data")
        case [".tar", ".xz"] | [_, ".txz"] | [".txz"]:
            with tarfile.open(file_path, "r:xz") as tar:
                tar.extractall(path=out_path, filter="data")
        case [_, ".tar"] | [".tar"]:
            with tarfile.open(file_path, "r:") as tar:
                tar.extractall(path=out_path, filter="data")
        case [_, ".gz"] | [".gz"]:
            with gzip.open(file_path, "rb") as f_in, (out_path / file_path.stem).open("wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        case [_, ".zip"] | [".zip"] | [_, ".vsix"] | [".vsix"]:
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(out_path)
        case _:
            raise ValueError(f"Unsupported file type: {file_path}")


def is_extractable(file_path: Path) -> bool:
    match file_path.suffixes[-2:]:
        case [".tar", ".gz"] | [_, ".tgz"] | [".tgz"]:
            return True
        case [".tar", ".bz2"] | [_, ".tbz2"] | [".tbz2"]:
            return True
        case [".tar", ".xz"] | [_, ".txz"] | [".txz"]:
            return True
        case [_, ".tar"] | [".tar"]:
            return True
        case [_, ".gz"] | [".gz"]:
            return True
        case [_, ".zip"] | [".zip"] | [_, ".vsix"] | [".vsix"]:
            return True
        case _:
            return False


def download_file(url: str, out_path: Path) -> None:
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        with (
            out_path.open("wb") as f,
            tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=f"Downloading {out_path.name}",
            ) as progress,
        ):
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                progress.update(len(chunk))


def download_github_release(repo: str, asset: str, version: Optional[str] = None, out_path=Path(".")) -> None:
    download_file(
        (
            f"https://github.com/{repo}/releases/download/{version}/{asset}"
            if version
            else f"https://github.com/{repo}/releases/latest/download/{asset}"
        ),
        out_path / asset,
    )


def select_by_os(unix: Any, windows: Any) -> Any:
    return windows if os.name == "nt" else unix


@lru_cache(maxsize=None)
def is_platform(targets: tuple[str]) -> bool:
    @lru_cache(maxsize=1)
    def current_targets() -> set[str]:
        system = platform.system().lower()
        arch = platform.machine().lower()
        arch_map = {"x86_64": "x64", "amd64": "x64", "i386": "x86", "i686": "x86", "aarch64": "arm64"}
        system_map = {"windows": "win"}
        system = system_map.get(system, system)
        arch = arch_map.get(arch, arch)
        targets = {system, f"{system}_{arch}"}
        if system in {"linux", "darwin"}:
            targets.add("unix")
        if system == "linux":
            targets.update({f"{system}_{arch}_gnu", f"{system}_{arch}_musl"})
        return targets

    return any(t in current_targets() for t in targets)


def safe_rmtree(dir: Path, base: Path):
    if not dir.is_dir() and dir.is_symlink():
        raise ValueError(f"'{dir}' is not a valid directory")
    if not str(dir.resolve()).startswith(str(base.resolve())):
        raise ValueError(f"'{dir}' is outside the trusted base directory")
    shutil.rmtree(dir)
