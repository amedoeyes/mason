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
            f"{pkg.package}.{pkg.version}",
        ],
        check=True,
    )


def bin_path(target: str) -> Path:
    return select_by_os(
        unix=Path("bin") / target,
        windows=Path("bin") / f"{target}.exe",
    )
