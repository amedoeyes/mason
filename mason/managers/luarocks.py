import os
from pathlib import Path
import platform
import subprocess
from mason.package import Package


def install(pkg: Package) -> None:
    cmd = ["luarocks", "install", "--tree", os.getcwd()]
    if pkg.params:
        if repo_url := pkg.params.get("repository_url"):
            cmd += ["--server", repo_url]
        if pkg.params.get("dev") == "true":
            cmd.append("--dev")
    cmd += [pkg.package, pkg.version]
    subprocess.run(cmd, check=True)


def bin_path(target: str) -> Path:
    if platform.system() != "Windows":
        return Path(f"bin/{target}")
    else:
        return Path(f"bin/{target}.bat")
