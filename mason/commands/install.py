import json
import os
from pathlib import Path
import platform
import subprocess
import textwrap
from typing import Any

from mason import config, managers
from mason.package import Package


def _create_symlink(source: Path, dist: Path) -> None:
    dist.parent.mkdir(parents=True, exist_ok=True)
    if dist.is_symlink():
        dist.unlink()
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
    path = Path(name)
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


def install(args: Any) -> None:
    packages = json.loads(config.registry_path.read_bytes())

    for name in args.package:
        pkg = next((p for p in packages if p["name"] == name), None)
        if not pkg:
            raise Exception(f"Package '{name}' not found")

        pkg = Package(pkg)
        if pkg.deprecation:
            raise Exception(f"Package '{pkg.name}' is deprecated: {pkg.deprecation}")

        pkg_dir = config.packages_dir / pkg.name
        pkg_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(pkg_dir)
        os.environ["PWD"] = os.getcwd()

        installer_map = {
            "cargo": managers.cargo.install,
            "github": managers.github.install,
            "npm": managers.npm.install,
            "pypi": managers.pypi.install,
        }
        if pkg.manager not in installer_map:
            raise Exception(f"Installer for '{pkg.manager}' is not implemented")
        print(f"installing '{pkg.name}'...")
        installer_map[pkg.manager](pkg)

        if pkg.build:
            print(f"Building '{pkg.name}'...")
            for cmd in pkg.build.cmds:
                print(f"Running {' '.join(cmd)}")
                subprocess.run(cmd, check=True, env=pkg.build.env)

        for name, path in (pkg.bin or {}).items():
            bin_path = Path()
            if ":" in path:
                manager, target = path.split(":")
                resolver_map = {
                    "cargo": managers.cargo.bin_path,
                    "dotnet": lambda target: _create_script(name, f"dotnet {Path(target).absolute()}"),
                    "exec": lambda target: _create_script(name, str(Path(target).absolute())),
                    "npm": managers.npm.bin_path,
                    "pypi": managers.pypi.bin_path,
                    "pyvenv": lambda target: _create_script(name, f"{Path('venv/bin/python').absolute()} -m {target}"),
                }
                if manager not in resolver_map:
                    raise Exception(f"resolver for '{manager}' is not implemented")
                bin_path = pkg_dir / resolver_map[manager](target)
            else:
                bin_path = pkg_dir / path
            if platform.system() != "Windows":
                bin_path.chmod(bin_path.stat().st_mode | 0o111)
            dist_path = config.bin_dir / name
            print(f"Linking '{name}' -> '{dist_path}'...")
            _create_symlink(bin_path, dist_path)

        for dist, path in (pkg.share or {}).items():
            dist_path = config.share_dir / dist
            share_path = pkg_dir / path
            if dist.endswith("/"):
                dist_path.mkdir(parents=True, exist_ok=True)
                for file in share_path.iterdir():
                    print(f"Linking '{file.name}' -> '{dist_path / file.name}'...")
                    _create_symlink(file, dist_path / file.name)
            else:
                print(f"Linking '{path}' -> '{dist_path}'...")
                _create_symlink(share_path, dist_path)
