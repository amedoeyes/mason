import os
import subprocess
from pathlib import Path

from mason.package import Package
from mason.utility import select_by_os


def install(pkg: Package) -> None:
    cmd = ["luarocks", "install", "--tree", os.getcwd()]
    if pkg.purl.qualifiers:
        if repo_url := pkg.purl.qualifiers.get("repository_url"):
            cmd += ["--server", repo_url]
        if pkg.purl.qualifiers.get("dev") == "true":
            cmd.append("--dev")
    cmd += [pkg.purl.name, pkg.purl.version]
    subprocess.run(cmd, check=True)
