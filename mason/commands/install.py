import json
import os
from pathlib import Path
import subprocess
import textwrap
from typing import Any

from mason import config, installers
from mason.package import Package
from mason.utility import select_by_os


def _create_symlink(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        for file in [f for f in source.rglob("*") if f.is_file()]:
            target = dest / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or target.exists():
                target.unlink()
            print(f"Linking '{file}' -> '{target}'")
            target.symlink_to(file)
    else:
        if dest.is_symlink():
            dest.unlink()
        print(f"Linking '{dest}' -> '{source}'...")
        dest.symlink_to(source)


def _create_script(name: str, command: str, env: dict[str, str | int] | None = None) -> Path:
    env = env or {}
    bash = textwrap.dedent("""\
        #!/usr/bin/env bash
        {}
        exec {} "$@"
    """)
    batch = textwrap.dedent("""\
        @ECHO off
        {}
        {} %*
    """)

    path = Path(select_by_os(unix=name, windows=f"{name}.cmd"))
    path.write_text(
        select_by_os(unix=bash, windows=batch).format(
            "\n".join([f"{select_by_os(unix='export', windows='SET')} {k}={v}" for k, v in env.items()]),
            command,
        ),
        encoding="utf-8",
    )
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

        pkg.dir.mkdir(parents=True, exist_ok=True)
        os.chdir(pkg.dir)
        os.environ["PWD"] = os.getcwd()

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
            "openvsx": installers.openvsx.install,
            "pypi": installers.pypi.install,
        }

        if pkg.purl.type not in installer_map:
            raise Exception(f"Installer for '{pkg.purl.type}' is not implemented")

        print(f"Installing '{pkg.purl.type}' package '{pkg.purl.name}@{pkg.purl.version}'...")
        installer_map[pkg.purl.type](pkg)

        if pkg.build:
            print(f"Building '{pkg.name}'...")
            for cmd in pkg.build.cmds:
                print(f"Running '{cmd}'")
                subprocess.run(cmd, check=True, env={**os.environ, **pkg.build.env}, shell=True)

        for name, path in (pkg.bin or {}).items():
            dest_path = config.bin_dir / name
            bin_path = Path()

            if ":" in path:
                type, target = path.split(":")
                match type:
                    case "cargo":
                        bin_path = Path("bin") / select_by_os(unix=target, windows=f"{target}.exe")
                    case "composer":
                        bin_path = Path("bin") / "vendor" / select_by_os(unix=target, windows=f"{target}.bat")
                    case "dotnet":
                        bin_path = _create_script(name, f'dotnet "{Path(target).absolute()}"')
                    case "exec":
                        bin_path = _create_script(name, str(Path(target).absolute()))
                    case "gem":
                        bin_path = _create_script(
                            name,
                            str(pkg.dir / "bin" / select_by_os(unix=target, windows=f"{target}.bat")),
                            {"GEM_PATH": f"{pkg.dir}{select_by_os(unix=':$GEM_PATH', windows=';%%GEM_PATH%%')}"},
                        )
                    case "golang":
                        bin_path = Path(select_by_os(unix=target, windows=f"{target}.exe"))
                    case "java-jar":
                        bin_path = _create_script(name, f'java -jar "{pkg.dir / target}"')
                    case "luarocks":
                        bin_path = Path("bin") / select_by_os(unix=target, windows=f"{target}.bat")
                    case "node":
                        bin_path = _create_script(name, f'node "{pkg.dir / target}"')
                    case "npm":
                        bin_path = Path("node_modules") / ".bin" / select_by_os(unix=target, windows=f"{target}.cmd")
                    case "nuget":
                        bin_path = select_by_os(unix=target, windows=f"{target}.exe")
                    case "opam":
                        bin_path = Path("bin") / select_by_os(unix=target, windows=f"{target}.exe")
                    case "php":
                        bin_path = _create_script(name, f'php "{pkg.dir / target}"')
                    case "pypi":
                        bin_path = Path("venv") / select_by_os(
                            unix=Path("bin") / target,
                            windows=Path("Scripts") / f"{target}.exe",
                        )
                    case "python":
                        bin_path = _create_script(
                            name,
                            f'{select_by_os(unix="python3", windows="python")} "{pkg.dir / target}"',
                        )
                    case "pyvenv":
                        bin_path = _create_script(name, f"{pkg.dir / 'venv/bin/python'} -m {target}")
                    case "ruby":
                        bin_path = _create_script(name, f'ruby "{pkg.dir / target}"')
                    case _:
                        raise Exception(f"Resolver for '{type}' is not implemented")
                bin_path = pkg.dir / bin_path
            else:
                bin_path = pkg.dir / path

            _create_symlink(bin_path, dest_path)

            if os.name == "posix":
                bin_path.chmod(bin_path.stat().st_mode | 0o111)

        for dest, path in (pkg.share or {}).items():
            _create_symlink(pkg.dir / path, config.share_dir / dest)

        for dest, path in (pkg.opt or {}).items():
            _create_symlink(pkg.dir / path, config.opt_dir / dest)
