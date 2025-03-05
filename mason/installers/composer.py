import subprocess
from pathlib import Path

from mason.package import Package
from mason.utility import select_by_os


def install(pkg: Package) -> None:
    subprocess.run(["composer", "init", "--no-interaction", "--stability=stable"], check=True)
    subprocess.run(["composer", "require", f"{pkg.purl.namespace}/{pkg.purl.name}:{pkg.purl.version}"], check=True)
