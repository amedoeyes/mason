from typing import Any

from mason.context import Context


def install(args: Any, ctx: Context) -> None:
    if args.update_registries:
        print("Updating registries...")
        ctx.update_registries()

    for name in args.package:
        pkg = ctx.package(name)
        if not pkg:
            raise ValueError(f"Package '{name}' not found")
        if pkg.deprecation:
            raise ValueError(f"Package '{pkg.name}' is deprecated: {pkg.deprecation}")
        print(f"Installing '{name}'...")
        pkg.install()
