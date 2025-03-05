import os
import subprocess
from pathlib import Path

from mason.package import Package
from mason.utility import select_by_os


def install(pkg: Package) -> None:
    subprocess.run(
        [
            "go",
            "install",
            "-v",
            f"{pkg.purl.namespace}/{pkg.purl.name}{f'/{pkg.purl.subpath}' if pkg.purl.subpath else ''}@{pkg.purl.version}",
        ],
        env={**os.environ, "GOBIN": os.getcwd()},
        check=True,
    )
