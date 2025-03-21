import argparse
import os
import sys
from pathlib import Path
from typing import Any, cast
import time

import argcomplete
import portalocker
from argcomplete.completers import ChoicesCompleter

from mason import config
from mason.context import Context
from mason.package import Package, Receipt


def acquire_lock():
    lockfile = open(config.data_dir / "mason.lock", "w")
    printed = False
    while True:
        try:
            portalocker.lock(lockfile, portalocker.LOCK_EX | portalocker.LOCK_NB)
            return lockfile
        except portalocker.LockException:
            if not printed:
                print("Another instance is running. Waiting...\r")
                printed = True
            time.sleep(1)


def install(ctx: Context, args: Any) -> None:
    lock = acquire_lock()
    for name in args.package:
        pkg = ctx.package(name)
        if not pkg:
            raise ValueError(f"Package '{name}' not found")
        if pkg.deprecation:
            raise ValueError(f"Package '{pkg.name}' is deprecated: {pkg.deprecation}")
        print(f"Installing '{name}'...")
        pkg.install()
    lock.close()
    os.remove(lock.name)


def uninstall(ctx: Context, args: Any) -> None:
    lock = acquire_lock()
    for name in args.package:
        pkg = ctx.package(name)
        if not pkg:
            raise ValueError(f"Package '{name}' not found")
        if name not in ctx.installed_package_names:
            raise ValueError(f"Package '{name}' is not installed")
        print(f"Uninstalling '{name}'...")
        pkg.uninstall()
    lock.close()
    os.remove(lock.name)


def update(ctx: Context, _) -> None:
    lock = acquire_lock()
    ctx.update_registries()
    lock.close()
    os.remove(lock.name)


def upgrade(ctx: Context, args: Any) -> None:
    lock = acquire_lock()
    pkgs_to_upgrade = []

    for name in args.package or ctx.installed_package_names:
        pkg = ctx.package(name)
        if not pkg:
            raise ValueError(f"Package '{name}' not found")
        if name not in ctx.installed_package_names:
            raise ValueError(f"Package '{name}' is not installed")
        rct = Receipt(pkg)
        if pkg.purl.version != rct.purl.version:
            pkgs_to_upgrade.append((pkg, rct))

    if len(pkgs_to_upgrade) > 0:
        for pkg, rct in pkgs_to_upgrade:
            print(f"{pkg.name} {rct.purl.version} -> {pkg.purl.version}")

        if input("Upgrade? [y/N]: ").strip().lower() == "y":
            for pkg, _ in pkgs_to_upgrade:
                pkg.uninstall()
                pkg.install()
    else:
        print("All packages are up to date")

    lock.close()
    os.remove(lock.name)


def list(ctx: Context, _) -> None:
    for pkg in (cast(Package, ctx.package(p)) for p in ctx.installed_package_names):
        print(f"{pkg.name}@{pkg.purl.version}")


def search(ctx: Context, args: Any) -> None:
    def match(package: Package):
        return (
            (not args.category or any(args.category.casefold() == c.casefold() for c in package.categories))
            and (
                not args.language
                or (package.languages and any(args.language.casefold() == l.casefold() for l in package.languages))
            )
            and (args.query in package.name or args.query in package.description)
        )

    for pkg in ctx.packages:
        if not match(pkg):
            continue
        print(f"{pkg.name} {pkg.purl.version}")
        if pkg.deprecation:
            print(f"    Deprecation: {pkg.deprecation}")
        print(f"    Description: {pkg.description}")
        print(f"    Homepage: {pkg.homepage}")
        print(f"    Categories: {', '.join(pkg.categories)}")
        if pkg.languages:
            print(f"    Languages: {', '.join(pkg.languages)}")
        print(f"    Licenses: {', '.join(pkg.licenses)}")
        print()


def main():
    try:
        for dir in [
            config.data_dir,
            config.registries_dir,
            config.packages_dir,
            config.bin_dir,
            config.share_dir,
            config.opt_dir,
        ]:
            dir.mkdir(parents=True, exist_ok=True)

        ctx = Context()

        def formatter(prog):
            return argparse.HelpFormatter(prog, width=80, max_help_position=1000)

        parser = argparse.ArgumentParser(formatter_class=formatter)
        subparsers = parser.add_subparsers(title="commands", dest="command")

        parser_install = subparsers.add_parser("install", help="install packages", formatter_class=formatter)
        parser_install.set_defaults(func=install)
        parser_install.add_argument("package", nargs="+").completer = ChoicesCompleter(ctx.package_names)

        parser_uninstall = subparsers.add_parser("uninstall", help="uninstall packages", formatter_class=formatter)
        parser_uninstall.set_defaults(func=uninstall)
        parser_uninstall.add_argument("package", nargs="+").completer = ChoicesCompleter(ctx.installed_package_names)

        parser_upgrade = subparsers.add_parser("upgrade", help="upgrade packages", formatter_class=formatter)
        parser_upgrade.set_defaults(func=upgrade)
        parser_upgrade.add_argument("package", nargs="*").completer = ChoicesCompleter(ctx.installed_package_names)

        parser_update = subparsers.add_parser("update", help="update repositories", formatter_class=formatter)
        parser_update.set_defaults(func=update)

        parser_list = subparsers.add_parser("list", help="list installed packages", formatter_class=formatter)
        parser_list.set_defaults(func=list)

        parser_search = subparsers.add_parser("search", help="search packages", formatter_class=formatter)
        parser_search.set_defaults(func=search)
        parser_search.add_argument("query", nargs="?", default="")
        parser_search.add_argument(
            "-c", "--category", choices=["dap", "formatter", "linter", "lsp"], help="specify category of package"
        )
        parser_search.add_argument("-l", "--language", help="specify language of package")

        argcomplete.autocomplete(parser)

        args = parser.parse_args()
        if args.command:
            args.func(ctx, args)
        else:
            parser.print_help()

    except Exception as e:
        print(f"{Path(sys.argv[0]).name}: {e}")
    except KeyboardInterrupt:
        pass
