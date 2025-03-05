import json
import os
from pathlib import Path
import platform
import subprocess
import textwrap
from typing import Any

from mason import config, installers
from mason.package import Package


def _create_symlink(source: Path, dist: Path) -> None:
    dist.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        for file in [f for f in source.rglob("*") if f.is_file()]:
            target = dist / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or target.exists():
                target.unlink()
            print(f"Linking '{file}' -> '{target}'")
            target.symlink_to(file)
    else:
        if dist.is_symlink():
            dist.unlink()
        print(f"Linking '{dist}' -> '{source}'...")
        dist.symlink_to(source)


def _create_script(name: str, command: str, env: dict[str, str | int] | None = None) -> Path:
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

    path = Path(name + (".cmd" if platform.system() == "Windows" else ""))
    path.write_text(
        (batch_template if platform.system() == "Windows" else bash_template).format(
            "\n".join([f"{'SET' if platform.system() == 'Windows' else 'export'} {k}={v}" for k, v in env.items()]),
            command,
        ),
        encoding="utf-8",
    )

    if platform.system() != "Windows":
        path.chmod(path.stat().st_mode | 0o111)

    return path


def _install(pkg: Package) -> None:
    installer_map = {
        "cargo": installers.cargo.install,
        "composer": installers.composer.install,
        "gem": installers.gem.install,
        "generic": installers.generic.install,
        "github": installers.github.install,
        "golang": installers.golang.install,
        "luarocks": installers.luarocks.install,
        "npm": installers.npm.install,
        "nuget": installers.nuget.install,
        "opam": installers.opam.install,
        "pypi": installers.pypi.install,
    }

    if pkg.purl.type not in installer_map:
        raise Exception(f"Installer for '{pkg.purl.type}' is not implemented")

    print(f"Installing '{pkg.purl.type}' package '{pkg.purl.name}@{pkg.purl.version}'...")
    installer_map[pkg.purl.type](pkg)


def _build(pkg: Package) -> None:
    if pkg.build:
        print(f"Building '{pkg.name}'...")
        for cmd in pkg.build.cmds:
            print(f"Running '{cmd}'")
            subprocess.run(cmd, check=True, env={**os.environ, **pkg.build.env}, shell=True)


def _link_bin(pkg: Package) -> None:
    for name, path in (pkg.bin or {}).items():
        dist_path = config.bin_dir / name
        bin_path = Path()

        if ":" in path:
            resolver_map = {
                "cargo": installers.cargo.bin_path,
                "composer": installers.composer.bin_path,
                "dotnet": lambda target: _create_script(name, f"dotnet {Path(target).absolute()}"),
                "exec": lambda target: _create_script(name, str(Path(target).absolute())),
                "gem": lambda target: _create_script(
                    name,
                    str(installers.gem.bin_path(target).absolute()),
                    {"GEM_PATH": f"{pkg.dir}{':$GEM_PATH' if platform.system() != 'Windows' else ';%%GEM_PATH%%'}"},
                ),
                "golang": installers.golang.bin_path,
                "luarocks": installers.luarocks.bin_path,
                "npm": installers.npm.bin_path,
                "nuget": installers.nuget.bin_path,
                "opam": installers.opam.bin_path,
                "pypi": installers.pypi.bin_path,
                "pyvenv": lambda target: _create_script(name, f"{Path('venv/bin/python').absolute()} -m {target}"),
            }

            type, target = path.split(":")
            if type not in resolver_map:
                raise Exception(f"Resolver for '{type}' is not implemented")

            bin_path = pkg.dir / resolver_map[type](target)
        else:
            bin_path = pkg.dir / path

        _create_symlink(bin_path, dist_path)

        if platform.system() != "Windows":
            bin_path.chmod(bin_path.stat().st_mode | 0o111)


def _link_share(pkg: Package) -> None:
    for dist, path in (pkg.share or {}).items():
        dist_path = config.share_dir / dist
        share_path = pkg.dir / path
        _create_symlink(share_path, dist_path)


def install(args: Any) -> None:
    packages = json.loads(config.registry_path.read_bytes())

    for name in args.package:
        pkg = next((p for p in packages if p["name"] == name), None)
        if not pkg:
            raise Exception(f"Package '{name}' not found")

        pkg = Package(pkg)
        if pkg.deprecation:
            raise Exception(f"Package '{pkg.name}' is deprecated: {pkg.deprecation}")

        pkg.dir.mkdir(parents=True, exist_ok=True)
        os.chdir(pkg.dir)
        os.environ["PWD"] = os.getcwd()

        _install(pkg)
        _build(pkg)
        _link_bin(pkg)
        _link_share(pkg)
