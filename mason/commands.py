import json
import os
from pathlib import Path
import platform
import subprocess
import textwrap

from mason import config, installers
from mason.package import Package


def _write_exec_script(path: Path, command: str, env: dict[str, str | int] | None = None):
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
    packages = json.loads(config.registry_path.read_bytes())

    pkg = next((p for p in packages if p["name"] == args.package), None)
    if not pkg:
        raise Exception(f"Package '{args.package}' not found")

    pkg = Package(pkg)
    if pkg.deprecation:
        raise Exception(f"Package '{pkg.name}' is deprecated: {pkg.deprecation}")

    package_dir = config.packages_dir / pkg.name
    package_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(package_dir)
    os.environ["PWD"] = os.getcwd()

    print(f"installing '{pkg.name}'...")
    match pkg.manager:
        case "cargo":
            installers.cargo(pkg)
        case "github":
            installers.github(pkg)
        case "npm":
            installers.npm(pkg)
        case "pypi":
            installers.pypi(pkg)
        case _:
            raise Exception(f"'{pkg.manager}' not implemented")

    if pkg.build:
        print(f"Building '{pkg.name}'...")
        for cmd in pkg.build.cmds:
            print(f"Running {' '.join(cmd)}")
            subprocess.run(cmd, check=True, env=pkg.build.env)

    for name, path in (pkg.bin or {}).items():
        bin_path = Path()
        if ":" in path:
            manager, bin = path.split(":")
            match manager:
                case "cargo":
                    bin_path = package_dir / (f"bin/{bin}" if platform.system() != "Windows" else f"bin/{bin}.exe")
                case "dotnet":
                    bin_path = package_dir / name
                    _write_exec_script(bin_path, f"dotnet {Path(bin).absolute()}")
                case "exec":
                    bin_path = package_dir / name
                    _write_exec_script(bin_path, str(Path(bin).absolute()))
                case "npm":
                    bin_path = package_dir / f"node_modules/.bin/{bin}"
                case "pypi":
                    bin_path = package_dir / f"venv/bin/{bin}"
                case "pyvenv":
                    bin_path = package_dir / name
                    _write_exec_script(bin_path, f"{package_dir / 'venv/bin/python'} -m {bin}")
                case _:
                    raise Exception(f"'{manager}' not implemented")
        else:
            bin_path = package_dir / path

        if platform.system() != "Windows":
            bin_path.chmod(bin_path.stat().st_mode | 0o111)
        dist_path = config.bin_dir / name
        print(f"Linking '{name}' -> '{dist_path}'...")
        if dist_path.is_symlink():
            dist_path.unlink()
        os.symlink(bin_path.absolute(), dist_path)

    for dist, path in (pkg.share or {}).items():
        dist_path = config.share_dir / dist
        share_path = package_dir / path
        if dist.endswith("/"):
            dist_path.mkdir(parents=True, exist_ok=True)
            for file in share_path.iterdir():
                file_path = dist_path / file.name
                print(f"Linking '{file.name}' -> '{file_path}'...")
                if file_path.is_symlink():
                    file_path.unlink()
                file_path.symlink_to(file)
        else:
            print(f"Linking '{path}' -> '{dist_path}'...")
            dist_path.parent.mkdir(parents=True, exist_ok=True)
            if dist_path.is_symlink():
                dist_path.unlink()
            dist_path.symlink_to(share_path)


def search(args) -> None:
    packages = json.loads(config.registry_path.read_bytes())

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
