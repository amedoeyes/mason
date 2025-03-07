from typing import Any

from mason.context import Context
from mason.package import Package


def search(args: Any, ctx: Context) -> None:
    def match(pkg):
        return (
            (not args.category or any(args.category.casefold() == c.casefold() for c in pkg["categories"]))
            and (not args.language or any(args.language.casefold() == l.casefold() for l in pkg["languages"]))
            and (args.query in pkg["name"] or args.query in pkg["description"])
        )

    for pkg in [Package(pkg) for _, pkg in ctx.packages.items() if match(pkg)]:
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
