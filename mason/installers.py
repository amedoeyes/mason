from pathlib import Path
import subprocess
from mason import config
from mason.downloaders import download_github_release
from mason.package import Package
from mason.utility import extract_file, is_extractable


def cargo(pkg: Package) -> None:
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


def github(pkg: Package) -> None:
    if pkg.files:
        for f in pkg.files:
            asset_path = Path(f)
            dist_path = Path(".")
            match f.split(":", 1):
                case [ref, dist] if dist.endswith("/"):
                    dist_path = Path(dist)
                    dist_path.mkdir(parents=True, exist_ok=True)
                    download_github_release(pkg.package, ref, pkg.version, dist_path)
                    asset_path = dist_path / ref
                case [ref, dist]:
                    download_github_release(pkg.package, ref, pkg.version)
                    asset_path = Path(ref).replace(dist)
                case _:
                    download_github_release(pkg.package, f, pkg.version)
            if is_extractable(asset_path):
                extract_file(asset_path, dist_path)
    else:
        if (config.packages_dir / pkg.name / ".git").exists():
            subprocess.run(["git", "fetch", "--depth=1", "--tags", "origin", pkg.version], check=True)
            subprocess.run(["git", "reset", "--hard", pkg.version], check=True)
        else:
            subprocess.run(
                ["git", "clone", "--depth=1", f"https://github.com/{pkg.package}.git", "--branch", pkg.version, "."],
                check=True,
            )


def npm(pkg: Package) -> None:
    subprocess.run(["npm", "install", f"{pkg.package}@{pkg.version}"], check=True)


def pypi(pkg: Package) -> None:
    extra = f"[{pkg.params['extra']}]" if "extra" in pkg.params else ""
    subprocess.run(["python", "-m", "venv", "venv"], check=True)
    subprocess.run(["./venv/bin/pip", "install", f"{pkg.package}{extra}=={pkg.version}"], check=True)
