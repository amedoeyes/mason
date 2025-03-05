import os
import platform
import subprocess
from pathlib import Path

from mason.package import Package


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


def bin_path(target: str) -> Path:
    if platform.system() != "Windows":
        return Path(f"{target}")
    else:
        return Path(f"{target}.exe")
