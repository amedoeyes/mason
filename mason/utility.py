import gzip
from pathlib import Path
import shutil
import tarfile
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
    return file_path.suffixes[-2:] == [".tar", ".gz"] or file_path.suffix in {".tgz", ".tar", ".gz", ".zip"}


def download_file(url: str, out_path: Path) -> None:
    print(f"Downloading '{url}'...")
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        with out_path.open("wb") as f, tqdm(total=total_size, unit="B", unit_scale=True, unit_divisor=1024) as progress:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                progress.update(len(chunk))
