import gzip
from pathlib import Path
import shutil
import tarfile
import zipfile


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
