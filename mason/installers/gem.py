import os
import subprocess
from pathlib import Path

from mason.package import Package
from mason.utility import select_by_os


def install(pkg: Package) -> None:
    subprocess.run(
        [
            "gem",
            "install",
            "--no-user-install",
            "--no-format-executable",
            "--install-dir=.",
            "--bindir=bin",
            "--no-document",
            f"{pkg.purl.name}:{pkg.purl.version}",
        ],
        env={"GEM_HOME": os.getcwd()},
        check=True,
    )
