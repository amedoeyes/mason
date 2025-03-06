import argparse
import json
import sys
from pathlib import Path

import argcomplete
from argcomplete.completers import ChoicesCompleter

from mason import commands, config, registry


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

        if not config.registry_path.exists():
            registry.download()

        def formatter(prog):
            return argparse.HelpFormatter(prog, width=80, max_help_position=1000)

        parser = argparse.ArgumentParser(formatter_class=formatter)
        parser.set_defaults(func=lambda _: None)

        subparsers = parser.add_subparsers()

        parser_install = subparsers.add_parser("install", help="install a specific package", formatter_class=formatter)
        parser_install.set_defaults(func=commands.install)
        parser_install.add_argument("package", nargs="+").completer = ChoicesCompleter(
            [pkg["name"] for pkg in json.loads(config.registry_path.read_bytes())]
        )

        parser_search = subparsers.add_parser("search", help="search registry", formatter_class=formatter)
        parser_search.set_defaults(func=commands.search)
        parser_search.add_argument("query", nargs="?", default="")
        parser_search.add_argument(
            "-c",
            "--category",
            choices=["dap", "formatter", "linter", "lsp"],
            metavar="CATEGORY",
            help="specify category for search",
        )
        parser_search.add_argument("-l", "--language", metavar="language", help="specify language for search")

        parser.add_argument("-u", "--update-registry", action="store_true", help="update mason registry")

        argcomplete.autocomplete(parser)

        if len(sys.argv) == 1:
            parser.print_help()
            sys.exit(1)

        args = parser.parse_args()

        if args.update_registry:
            registry.update()

        args.func(args)

    except Exception as e:
        print(f"{Path(sys.argv[0]).name}: {e}")
