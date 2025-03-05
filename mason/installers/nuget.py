import subprocess
from pathlib import Path

from mason.package import Package
from mason.utility import select_by_os


def install(pkg: Package) -> None:
    subprocess.run(
        [
            "dotnet",
            "tool",
            "update",
            "--tool-path",
            ".",
            "--version",
            pkg.purl.version,
            pkg.purl.name,
        ],
        check=True,
    )
