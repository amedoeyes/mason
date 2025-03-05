from pathlib import Path

from mason.package import Package
from mason.utility import download_file, extract_file, is_extractable


def install(pkg: Package) -> None:
    for name, url in (pkg.files if isinstance(pkg.files, dict) else {}).items():
        out_path = Path(name)
        download_file(url, out_path)
        if is_extractable(out_path):
            extract_file(out_path)
