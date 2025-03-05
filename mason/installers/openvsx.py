from pathlib import Path

from mason.package import Package
from mason.utility import download_file, extract_file


def install(pkg: Package) -> None:
    for file in pkg.files or []:
        out_path = Path(file)
        download_file(
            f"https://open-vsx.org/api/{pkg.purl.namespace}/{pkg.purl.name}/{pkg.purl.version}/file/{file}",
            out_path,
        )
        extract_file(out_path)
