from pathlib import Path

from mason.package import Package
from mason.utility import download_file, extract_file, is_extractable


def install(pkg: Package) -> None:
    out_path = Path(*pkg.files)
    download_file(
        f"https://open-vsx.org/api/{pkg.purl.namespace}/{pkg.purl.name}/{pkg.purl.version}/file/{pkg.files[0]}",
        out_path,
    )
    if is_extractable(out_path):
        extract_file(out_path)
