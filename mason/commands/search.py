from typing import Any

from mason.context import Context
from mason.package import Package


def search(args: Any, ctx: Context) -> None:
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
