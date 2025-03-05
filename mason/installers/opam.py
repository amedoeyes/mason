import subprocess
from pathlib import Path

from mason.package import Package
from mason.utility import select_by_os


def install(pkg: Package) -> None:
    subprocess.run(
        [
            "opam",
            "install",
            "--destdir=.",
            "--yes",
            "--verbose",
            f"{pkg.purl.name}.{pkg.purl.version}",
        ],
        check=True,
    )


def bin_path(target: str) -> Path:
    return Path("bin") / select_by_os(unix=target, windows=f"{target}.exe")
