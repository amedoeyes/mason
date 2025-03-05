import os
import platform
import subprocess
from pathlib import Path

from mason.package import Package


def install(pkg: Package) -> None:
    cmd = ["luarocks", "install", "--tree", os.getcwd()]
    if pkg.purl.qualifiers:
        if repo_url := pkg.purl.qualifiers.get("repository_url"):
            cmd += ["--server", repo_url]
        if pkg.purl.qualifiers.get("dev") == "true":
            cmd.append("--dev")
    cmd += [pkg.purl.name, pkg.purl.version]
    subprocess.run(cmd, check=True)


def bin_path(target: str) -> Path:
    if platform.system() != "Windows":
        return Path(f"bin/{target}")
    else:
        return Path(f"bin/{target}.bat")
