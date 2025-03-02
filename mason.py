import argparse
import gzip
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import textwrap
import zipfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote

import requests
from jinja2 import Environment
from tqdm import tqdm

MASON_REPO = os.getenv("MASON_REPO", "mason-org/mason-registry")
MASON_CACHE_DIR = Path(
    os.getenv("MASON_CACHE_DIR", os.path.join(os.getenv("XDG_CACHE_HOME", "~/.cache"), "mason"))
).expanduser()
MASON_DATA_DIR = Path(
    os.getenv("MASON_DATA_DIR", os.path.join(os.getenv("XDG_DATA_HOME", "~/.local/share"), "mason"))
).expanduser()
MASON_BIN_DIR = MASON_DATA_DIR / "bin"
MASON_SHARE_DIR = MASON_DATA_DIR / "share"
MASON_PACKAGES_DIR = MASON_DATA_DIR / "packages"
MASON_REGISTRY = MASON_CACHE_DIR / "registry.json"


def extract_file(file_path: Path, out_path=Path(".")) -> None:
    print(f"Extracting '{file_path}'...")
    match file_path.suffixes[-2:]:
        case [".tar", ".gz"] | [_, ".tgz"] | [".tgz"]:
            with tarfile.open(file_path, "r:gz") as tar:
                tar.extractall(path=out_path, filter="data")
        case [_, ".tar"] | [".tar"]:
            with tarfile.open(file_path, "r:") as tar:
                tar.extractall(path=out_path, filter="data")
        case [_, ".gz"] | [".gz"]:
            with gzip.open(file_path, "rb") as f_in, (out_path / file_path.stem).open("wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        case [_, ".zip"] | [".zip"]:
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(out_path)
        case _:
            raise ValueError(f"Unsupported file type: {file_path}")


def is_extractable(file_path: Path) -> bool:
    return file_path.suffixes[-2:] == [".tar", ".gz"] or file_path.suffix in {".tgz", ".tar", ".gz", ".zip"}


def verify_checksums(checksum_file: Path) -> bool:
    for line in checksum_file.read_text():
        expected_hash, file = line.split()
        file_path = checksum_file.parent / file
        if not file_path.exists() or hashlib.sha256(file_path.read_bytes()).hexdigest() != expected_hash:
            return False
    return True


def download_file(url: str, out_path: Path) -> None:
    print(f"Downloading '{url}'...")
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        with out_path.open("wb") as f, tqdm(total=total_size, unit="B", unit_scale=True, unit_divisor=1024) as progress:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                progress.update(len(chunk))


def download_github_release(repo: str, asset: str, version="latest", out_path=Path(".")) -> None:
    if version != "latest":
        version = f"tags/{version}"
    response = requests.get(f"https://api.github.com/repos/{repo}/releases/{version}")
    response.raise_for_status()
    download_link = next((a["browser_download_url"] for a in response.json()["assets"] if a["name"] == asset), None)
    if not download_link:
        raise ValueError(f"Asset '{asset}' not found in release '{version}'")
    download_file(download_link, out_path / asset)


def download_registry() -> None:
    checksums_file = MASON_CACHE_DIR / "checksums.txt"
    if checksums_file.exists():
        print("Checking for update...")
    download_github_release(MASON_REPO, "checksums.txt", "latest", MASON_CACHE_DIR)
    if verify_checksums(checksums_file):
        print("Registry up-to-date")
        return
    print("Downloading registry..." if not MASON_REGISTRY.exists() else "Updating registry...")
    download_github_release(MASON_REPO, "registry.json.zip", "latest", MASON_CACHE_DIR)
    extract_file(MASON_CACHE_DIR / "registry.json.zip", MASON_CACHE_DIR)


def is_platform(target: str | list[str]) -> bool:
    system = platform.system().lower()
    arch = platform.machine().lower()
    arch_map = {
        "x86_64": "x64",
        "amd64": "x64",
        "i386": "x86",
        "i686": "x86",
        "arm": "arm",
        "aarch64": "arm64",
        "armv6l": "armv6l",
        "armv7l": "armv7l",
    }
    system_map = {
        "linux": "linux",
        "darwin": "darwin",
        "windows": "win",
    }
    libc = None
    if system == "linux":
        result = subprocess.run(["ldd", "--version"], capture_output=True, text=True)
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        libc = "musl" if "musl" in first_line else "gnu" if any(s in first_line for s in {"glibc", "GNU"}) else None
    possible_targets = [
        f"{system_map[system]}_{arch_map[arch]}",
        "win" if system == "windows" else "unix",
    ]
    if system == "linux":
        possible_targets.append("linux")
    if libc:
        possible_targets.append(f"{system_map[system]}_{arch_map[arch]}_{libc}")
    return any(t in possible_targets for t in (target if isinstance(target, list) else [target]))


def parse_source_id(source_id: str) -> tuple[str, str, str, dict[str, str] | None]:
    manager, rest = source_id[4:].split("/", 1)
    package, rest = rest.split("@", 1)
    version, rest = (rest.split("?", 1) + [""])[:2]
    params = {k: v for param in rest.split("&") for k, v in [param.split("=", 1)]} if rest else None
    return (manager, unquote(package), unquote(version), params)


def to_jinja_syntax(s):
    s = re.sub(r"\|\|", "|", s)
    s = re.sub(r'strip_prefix\s*\\?"(.*?)\\?"', r'strip_prefix("\1")', s)
    return s


class Asset:
    files: list[str]
    bin: Optional[str | dict[str, str]]

    def __init__(self, data: Any) -> None:
        self.files = [data["file"]] if isinstance(data["file"], str) else data["file"]
        self.bin = data.get("bin", None)

    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(f'{k}={v!r}' for k, v in vars(self).items())})"


class Build:
    cmds: list[list[str]]
    env: dict[str, str]

    def __init__(self, data: Any) -> None:
        self.cmds = [shlex.split(os.path.expandvars(cmd)) for cmd in data["run"].splitlines()]
        self.env = data.get("env", {})

    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(f'{k}={v!r}' for k, v in vars(self).items())})"


class Package:
    name: str
    description: str
    homepage: str
    licenses: list[str]
    languages: Optional[list[str]]
    categories: list[str]
    deprecation: Optional[str]
    package: str
    version: str
    manager: str
    params: dict[str, str]
    asset: Optional[Asset]
    build: Optional[Build]
    bin: Optional[dict[str, str]]
    share: Optional[dict[str, str]]

    def __init__(self, data: Any) -> None:
        self.name = data["name"]
        self.homepage = data["homepage"]
        self.licenses = data["licenses"]
        self.languages = data["languages"]
        self.categories = data["categories"]
        self.description = data["description"].replace("\n", " ").strip()
        self.deprecation = data["deprecation"]["message"] if "deprecation" in data else None
        self.manager, rest = data["source"]["id"][4:].split("/", 1)
        self.package, rest = rest.split("@", 1)
        self.version, rest = (rest.split("?", 1) + [""])[:2]
        self.params = {k: v for param in rest.split("&") for k, v in [param.split("=", 1)]} if rest else {}

        env = Environment()
        env.filters["take_if_not"] = lambda value, cond: value if not cond else None
        env.filters["strip_prefix"] = lambda value, prefix: value[len(prefix) :] if value.startswith(prefix) else value
        env.globals["is_platform"] = is_platform
        env.globals["version"] = self.version

        assets = data["source"].get("asset", None)
        if isinstance(assets, list):
            data["source"]["asset"] = next((a for a in assets if is_platform(a.get("target"))), None)

        builds = data["source"].get("build", None)
        if isinstance(builds, list):
            data["source"]["build"] = next((a for a in builds if is_platform(a.get("target"))), None)

        env.globals.update(data)

        data_str = json.dumps(data, indent=2)
        data_str = env.from_string(to_jinja_syntax(data_str)).render()
        data_str = env.from_string(to_jinja_syntax(data_str)).render()  # have to do 2 passes because nesting :/
        data = json.loads(data_str)

        self.asset = Asset(asset) if (asset := data["source"].get("asset")) else None
        self.build = Build(build) if (build := data["source"].get("build")) else None
        self.bin = data.get("bin", None)
        self.share = data.get("share", None)

    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(f'{k}={v!r}' for k, v in vars(self).items())})"


def write_exec_script(path: Path, command: str, env: dict[str, str | int] | None = None):
    env = env or {}
    bash_template = textwrap.dedent("""\
        #!/usr/bin/env bash
        {}
        exec {} "$@"
    """)
    batch_template = textwrap.dedent("""\
        @ECHO off
        {}
        {} %*
    """)
    path.write_text(
        (batch_template if platform.system() == "Windows" else bash_template).format(
            "\n".join([f"{'SET' if platform.system() == 'Windows' else 'export'} {k}={v}" for k, v in env.items()]),
            command,
        ),
        encoding="utf-8",
    )
    if platform.system() != "Windows":
        path.chmod(path.stat().st_mode | 0o111)


def install(args) -> None:
    packages = json.loads(MASON_REGISTRY.read_bytes())
    pkg = next((p for p in packages if p["name"] == args.package), None)
    if not pkg:
        raise Exception(f"Package '{args.package}' not found")

    pkg = Package(pkg)
    if pkg.deprecation:
        raise Exception(f"Package '{pkg.name}' is deprecated: {pkg.deprecation}")

    package_dir = MASON_PACKAGES_DIR / pkg.name
    package_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(package_dir)
    os.environ["PWD"] = os.getcwd()

    match pkg.manager:
        case "npm":
            subprocess.run(["npm", "install", f"{pkg.package}@{pkg.version}"])
        case "pypi":
            extra = f"[{pkg.params['extra']}]" if "extra" in pkg.params else ""
            subprocess.run(["python", "-m", "venv", "venv"])
            subprocess.run(["./venv/bin/pip", "install", f"{pkg.package}{extra}=={pkg.version}"])
        case "github":
            if pkg.asset:
                for f in pkg.asset.files:
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
                if (package_dir / ".git").exists():
                    subprocess.run(["git", "fetch", "--depth=1", "--tags", "origin", pkg.version], check=True)
                    subprocess.run(["git", "reset", "--hard", pkg.version], check=True)
                else:
                    subprocess.run(
                        [
                            "git",
                            "clone",
                            "--depth=1",
                            f"https://github.com/{pkg.package}.git",
                            "--branch",
                            pkg.version,
                            ".",
                        ],
                        check=True,
                    )
        case "cargo":
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
            subprocess.run(cmd)
        case _:
            raise Exception(f"'{pkg.manager}' not implemented")

    if pkg.build:
        print("Building...")
        for cmd in pkg.build.cmds:
            print(f"Running {' '.join(cmd)}")
            subprocess.run(cmd, check=True, env=pkg.build.env)

    for key, value in (pkg.bin or {}).items():
        bin_path = Path()
        if ":" in value:
            manager, bin = value.split(":")
            match manager:
                case "npm":
                    bin_path = package_dir / f"node_modules/.bin/{bin}"
                case "pypi":
                    bin_path = package_dir / f"venv/bin/{bin}"
                case "exec":
                    bin_path = package_dir / key
                    write_exec_script(bin_path, str(Path(bin).absolute()))
                case "dotnet":
                    bin_path = package_dir / key
                    write_exec_script(bin_path, f"dotnet {Path(bin).absolute()}")
                case "pyvenv":
                    bin_path = package_dir / key
                    write_exec_script(bin_path, f"{package_dir / 'venv/bin/python'} -m {bin}")
                case "cargo":
                    if platform.system() == "Windows":
                        bin_path = package_dir / f"bin/{bin}.exe"
                    else:
                        bin_path = package_dir / f"bin/{bin}"
                case _:
                    raise Exception(f"'{manager}' not implemented")
        else:
            bin_path = package_dir / value
        if platform.system() != "Windows":
            bin_path.chmod(bin_path.stat().st_mode | 0o111)
        dist = MASON_BIN_DIR / key
        if dist.is_symlink():
            dist.unlink()
        os.symlink(bin_path.absolute(), dist)

    for key, value in (pkg.share or {}).items():
        dist = MASON_SHARE_DIR / key
        share_path = package_dir / value
        if key.endswith("/"):
            dist.mkdir(parents=True, exist_ok=True)
            for file in share_path.iterdir():
                dist = dist / file.name
                if dist.is_symlink():
                    dist.unlink()
                dist.symlink_to(file)
        else:
            dist.parent.mkdir(parents=True, exist_ok=True)
            if dist.is_symlink():
                dist.unlink()
            dist.symlink_to(share_path)


def search(args) -> None:
    packages = json.loads(MASON_REGISTRY.read_bytes())

    def matches(pkg):
        return (
            (not args.category or any(args.category.casefold() == c.casefold() for c in pkg["categories"]))
            and (not args.language or any(args.language.casefold() == l.casefold() for l in pkg["languages"]))
            and (args.query in pkg["name"] or args.query in pkg["description"])
        )

    for pkg in map(lambda pkg: Package(pkg), filter(matches, packages)):
        print(f"{pkg.name} {pkg.version}")
        if pkg.deprecation:
            print(f"    Deprecation: {pkg.deprecation}")
        print(f"    Description: {pkg.description}")
        print(f"    Homepage: {pkg.homepage}")
        print(f"    Categories: {', '.join(pkg.categories)}")
        if pkg.languages:
            print(f"    Languages: {', '.join(pkg.languages)}")
        print(f"    Licenses: {', '.join(pkg.licenses)}")
        print()


if __name__ == "__main__":
    try:
        for dir in [MASON_CACHE_DIR, MASON_DATA_DIR, MASON_BIN_DIR, MASON_SHARE_DIR, MASON_PACKAGES_DIR]:
            dir.mkdir(parents=True, exist_ok=True)

        if not MASON_REGISTRY.exists():
            download_registry()

        def formatter(prog):
            return argparse.HelpFormatter(prog, width=80, max_help_position=1000)

        parser = argparse.ArgumentParser(formatter_class=formatter)
        parser.set_defaults(func=lambda _: None)
        subparsers = parser.add_subparsers()

        parser_install = subparsers.add_parser("install", help="install a specific package", formatter_class=formatter)
        parser_install.set_defaults(func=install)
        parser_install.add_argument("package", help="name of package to install")

        parser_search = subparsers.add_parser("search", help="search registry", formatter_class=formatter)
        parser_search.set_defaults(func=search)
        parser_search.add_argument("query", nargs="?", default="", help="search query")
        parser_search.add_argument(
            "-c",
            "--category",
            choices=["dap", "formatter", "linter", "lsp"],
            metavar="CATEGORY",
            help="specify category for search",
        )
        parser_search.add_argument("-l", "--language", metavar="language", help="specify language for search")

        parser.add_argument("-u", "--update-registry", action="store_true", help="update mason registry")

        if len(sys.argv) == 1:
            parser.print_help()
            sys.exit(1)

        args = parser.parse_args()

        if args.update_registry:
            download_registry()

        args.func(args)

    except Exception as e:
        print(f"{sys.argv[0]}: {e}")
