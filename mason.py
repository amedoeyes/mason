#!/bin/python3

import textwrap
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
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests
from jinja2 import Template

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


def extract_file(file_path: Path, extract_path=Path(".")) -> None:
    print(f"Extracting '{file_path}'...")
    if file_path.suffixes[-2:] == [".tar", ".gz"] or file_path.suffix == ".tgz":
        with tarfile.open(file_path, "r:gz") as tar:
            tar.extractall(path=extract_path, filter="data")
    elif file_path.suffix == ".tar":
        with tarfile.open(file_path, "r:") as tar:
            tar.extractall(path=extract_path, filter="data")
    elif file_path.suffix == ".gz":
        output_file = extract_path / file_path.stem
        with gzip.open(file_path, "rb") as f_in, open(output_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    elif file_path.suffix == ".zip":
        with zipfile.ZipFile(file_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)
    else:
        raise Exception(f"Unsupported file type: {file_path}")


def extractable(file_path: Path) -> bool:
    if file_path.suffixes[-2:] == [".tar", ".gz"] or file_path.suffix == ".tgz":
        return True
    elif file_path.suffix == ".tar":
        return True
    elif file_path.suffix == ".gz":
        return True
    elif file_path.suffix == ".zip":
        return True
    else:
        return False


def verify_checksums(checksum_file: Path) -> bool:
    with open(checksum_file, "r") as f:
        try:
            for line in f:
                expected_hash, file = line.split()
                with open(checksum_file.parent / file, "rb") as f:
                    if hashlib.file_digest(f, "sha256").hexdigest() != expected_hash:
                        return False
        except FileNotFoundError:
            return False
    return True


def download_github_release(repo: str, asset: str, version="latest", directory=Path(".")) -> None:
    if version != "latest":
        version = f"tags/{version}"

    response = requests.get(f"https://api.github.com/repos/{repo}/releases/{version}")
    release_data = response.json()

    download_link = next((a["browser_download_url"] for a in release_data["assets"] if a["name"] == asset), None)
    if not download_link:
        raise ValueError(f"Asset {asset} not found in release {version}")

    print(f"Downloading '{download_link}'...")
    response = requests.get(download_link, stream=True)

    with (directory / asset).open("wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def download_registry() -> None:
    checksums_file = MASON_CACHE_DIR / "checksums.txt"
    if checksums_file.exists():
        print("Checking for update...")
    download_github_release(MASON_REPO, "checksums.txt", "latest", MASON_CACHE_DIR)
    if not verify_checksums(checksums_file):
        if not MASON_REGISTRY.exists():
            print("Downloading registry...")
        else:
            print("Updating registry...")
        download_github_release(MASON_REPO, "registry.json.zip", "latest", MASON_CACHE_DIR)
        extract_file(MASON_CACHE_DIR / "registry.json.zip")
    else:
        print("Registry up-to-date")


def is_current_target(target: str | list[str]) -> bool:
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

    result = subprocess.run(["ldd", "--version"], capture_output=True)
    first_line = str(result.stdout.splitlines()[0])
    libc = ""
    if "musl" in first_line:
        libc = "musl"
    elif "glibc" in first_line or "GNU" in first_line:
        libc = "gnu"

    possible_targets = {system, f"{system_map[system]}_{arch_map[arch]}"}
    possible_targets.add(f"{system_map[system]}_{arch_map[arch]}_{libc}")

    if system in {"linux", "darwin"}:
        possible_targets.add("unix")
    elif system == "windows":
        possible_targets.add("win")

    match target:
        case str():
            return target in possible_targets
        case list():
            return any(t in possible_targets for t in target)


def parse_source_id(source_id: str) -> tuple[str, str, str, dict | None]:
    type, rest = source_id[4:].split("/", 1)
    package, rest = rest.split("@", 1)
    version = ""
    args = None
    if "?" in rest:
        version, rest = rest.split("?", 1)
        key, value = rest.split("=", 1)
        args = {key: value}
    else:
        version = rest
    return (type, unquote(package), unquote(version), args)


def get_pkg(name: str) -> Any:
    def to_jinja_syntax(s):
        return re.sub(r"\|\|?\s*strip_prefix\s*\\?\"(.*?)\\?\"", r"| replace('\1', '')", s)

    def process(obj, ctx):
        match obj:
            case dict():
                return {k: process(v, ctx) for k, v in obj.items()}
            case list():
                return [process(v, ctx) for v in obj]
            case str():
                return Template(to_jinja_syntax(obj)).render(ctx)
            case _:
                return obj

    with open(MASON_REGISTRY, "r") as f:
        packages = json.load(f)

    pkg = next((p for p in packages if p["name"] == name), None)
    if not pkg:
        raise Exception(f"Package '{name}' not found")

    _, _, version, _ = parse_source_id(pkg["source"]["id"])

    pkg = process(
        pkg,
        {
            "version": version,
            "source": {
                "asset": next((a for a in pkg["source"].get("asset", []) if is_current_target(a.get("target"))), None),
                "build": next((b for b in pkg["source"].get("build", []) if is_current_target(b.get("target"))), None),
            },
        },
    )

    return pkg


def write_exec_script(path: Path, command: str, env: dict[str, str | int] = {}):
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
    if platform.system() == "Windows":
        with path.open("w") as f:
            f.write(batch_template.format("\n".join([f"SET {k}={v}" for k, v in env.items()]), command))
    else:
        with path.open("w") as f:
            f.write(bash_template.format("\n".join([f"export {k}={v}" for k, v in env.items()]), command))
        path.chmod(path.stat().st_mode | 0o111)


def install(args) -> None:
    pkg = get_pkg(args.package)
    type, package, version, pargs = parse_source_id(pkg["source"]["id"])

    package_dir = MASON_PACKAGES_DIR / args.package
    package_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(package_dir)
    os.environ["PWD"] = os.getcwd()

    match type:
        case "npm":
            subprocess.run(["npm", "install", f"{package}@{version}"])
        case "pypi":
            extra = f"[{pargs['extra']}]" if pargs is not None else ""
            subprocess.run(["python", "-m", "venv", "venv"])
            subprocess.run(["./venv/bin/pip", "install", f"{package}{extra}=={version}"])
        case "github":

            def process_asset(asset: str) -> None:
                if ":" in asset:
                    ref, dist = asset.split(":", 1)
                    if dist[-1] == "/":
                        dist = Path(dist)
                        dist.mkdir(parents=True, exist_ok=True)
                        download_github_release(package, ref, version, dist)
                        asset_path = dist / ref
                        if extractable(asset_path):
                            extract_file(asset_path, dist)
                    else:
                        download_github_release(package, ref, version)
                        asset_path = Path(ref).replace(dist)
                        if extractable(asset_path):
                            extract_file(asset_path)
                else:
                    download_github_release(package, asset, version)
                    asset_path = Path(asset)
                    if extractable(asset_path):
                        extract_file(asset_path)

            if "asset" in pkg["source"]:
                asset = next((a["file"] for a in pkg["source"]["asset"] if is_current_target(a["target"])), None)
                if asset is None:
                    raise Exception("Could not find asset")
                assets = asset if isinstance(asset, list) else [asset]
                for a in assets:
                    process_asset(a)
            else:
                if (package_dir / ".git").exists():
                    subprocess.run(["git", "fetch", "--depth=1", "--tags", "origin", version], check=True)
                    subprocess.run(["git", "reset", "--hard", version], check=True)
                else:
                    subprocess.run(
                        ["git", "clone", "--depth=1", f"https://github.com/{package}.git", "--branch", version, "."],
                        check=True,
                    )
        case _:
            raise Exception(f"'{type}' not implemented")

    if "build" in pkg["source"]:
        print("Building...")
        build = next((a["run"] for a in pkg["source"]["build"] if is_current_target(a["target"])), None)
        if build is None:
            raise Exception("Could not find build")
        for cmd in build.splitlines():
            print(f"Running '{cmd}'")
            if cmd.strip():
                subprocess.run(shlex.split(os.path.expandvars(cmd)), check=True)

    for key, value in pkg.get("bin", {}).items():
        bin_path = Path()
        if ":" in value:
            type, bin = value.split(":")
            match type:
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
                case _:
                    raise Exception(f"'{type}' not implemented")
        else:
            bin_path = package_dir / value
        dist = MASON_BIN_DIR / key
        if dist.is_symlink():
            dist.unlink()
        os.symlink(bin_path.absolute(), dist)

    for key, value in pkg.get("share", {}).items():
        dist_dir = MASON_SHARE_DIR / key
        share_path = package_dir / value
        dist_dir.mkdir(parents=True, exist_ok=True)
        for file in share_path.iterdir():
            dist = dist_dir / file.name
            if dist.is_symlink():
                dist.unlink()
            dist.symlink_to(file)


def search(args) -> None:
    with open(MASON_REGISTRY, "r") as f:
        packages = json.load(f)
    for pkg in packages:
        cat = not args.category or any(args.category.lower() == cat.lower() for cat in pkg["categories"])
        lang = not args.language or any(args.language.lower() == lang.lower() for lang in pkg["languages"])
        name = args.query in pkg["name"]
        desc = args.query in pkg["description"]
        if (name or desc) and cat and lang:
            print(pkg["name"])
            print(f"    {pkg['description'].rstrip('\n').replace('\n', ' ')}")
            print(f"    Categories: {', '.join(pkg['categories'])}")
            if len(pkg["languages"]) > 0:
                print(f"    Languages: {', '.join(pkg['languages'])}")
            print(f"    Licenses: {', '.join(pkg['licenses'])}")
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
