from typing import Any

from mason.context import Context


def install(args: Any, ctx: Context) -> None:
    if args.update_registries:
        ctx.update_registries()

    for name in args.package:
        pkg = ctx.package(name)
        if not pkg:
            raise Exception(f"Package '{name}' not found")

        if pkg.deprecation:
            raise Exception(f"Package '{pkg.name}' is deprecated: {pkg.deprecation}")

        pkg.install()
