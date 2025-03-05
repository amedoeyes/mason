import gzip
import os
from pathlib import Path
import shutil
import tarfile
from typing import Any
import zipfile

import requests
from tqdm import tqdm


def extract_file(file_path: Path, out_path=Path(".")) -> None:
    print(f"Extracting '{file_path}'...")
    match file_path.suffixes[-2:]:
        case [".tar", ".gz"] | [_, ".tgz"] | [".tgz"]:
            with tarfile.open(file_path, "r:gz") as tar:
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
    return file_path.suffixes[-2:] == [".tar", ".gz"] or file_path.suffix in {".tgz", ".tar", ".gz", ".zip", ".vsix"}


def download_file(url: str, out_path: Path) -> None:
    print(f"Downloading '{url}'...")
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        with out_path.open("wb") as f, tqdm(total=total_size, unit="B", unit_scale=True, unit_divisor=1024) as progress:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                progress.update(len(chunk))


def download_github_release(repo: str, asset: str, version="latest", out_path=Path(".")) -> None:
    if version != "latest":
        version = f"tags/{version}"
    response = requests.get(f"https://api.github.com/repos/{repo}/releases/{version}")
    response.raise_for_status()
    download_link = next((a["browser_download_url"] for a in response.json()["assets"] if a["name"] == asset), None)
    if not download_link:
        raise ValueError(f"Asset '{asset}' not found in release '{version}'")
    download_file(download_link, out_path / asset)


def select_by_os(unix: Any, windows: Any) -> Any:
    return windows if os.name == "nt" else unix
