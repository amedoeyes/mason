from pathlib import Path
import subprocess
from mason.package import Package


def install(pkg: Package) -> None:
    cmd = ["cargo", "install", "--root", "."]
    if pkg.params:
        if repo_url := pkg.params.get("repository_url"):
            cmd += ["--git", repo_url]
            cmd += ["--rev" if pkg.params.get("rev") == "true" else "--tag", pkg.version]
        else:
            cmd += ["--version", pkg.version]
        if features := pkg.params.get("features"):
            cmd += ["--features", features]
        if pkg.params.get("locked") == "true":
            cmd.append("--locked")
    cmd.append(pkg.package)
    subprocess.run(cmd, check=True)


def bin_path(target: str) -> Path:
    return Path(f"node_modules/.bin/{target}")
