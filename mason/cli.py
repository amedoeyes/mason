import argparse
import sys
from pathlib import Path

import argcomplete
from argcomplete.completers import ChoicesCompleter

from mason import commands, config
from mason.context import Context


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
        parser.set_defaults(func=lambda _: None)

        subparsers = parser.add_subparsers()

        parser_install = subparsers.add_parser("install", help="install packages", formatter_class=formatter)
        parser_install.set_defaults(func=lambda args: commands.install(args, ctx))
        parser_install.add_argument("-u", "--update-registries", action="store_true", help="update registries")
        parser_install.add_argument("package", nargs="+").completer = ChoicesCompleter([pkg for pkg in ctx.packages])

        parser_list = subparsers.add_parser("list", help="list installed packages", formatter_class=formatter)
        parser_list.set_defaults(func=lambda _: commands.list())

        parser_search = subparsers.add_parser("search", help="search packages", formatter_class=formatter)
        parser_search.set_defaults(func=lambda args: commands.search(args, ctx))
        parser_search.add_argument("query", nargs="?", default="")
        parser_search.add_argument(
            "-c",
            "--category",
            choices=["dap", "formatter", "linter", "lsp"],
            metavar="CATEGORY",
            help="specify category for search",
        )
        parser_search.add_argument("-l", "--language", metavar="language", help="specify language for search")

        argcomplete.autocomplete(parser)

        if len(sys.argv) == 1:
            parser.print_help()
            sys.exit(1)

        args = parser.parse_args()

        args.func(args)

    except Exception as e:
        print(f"{Path(sys.argv[0]).name}: {e}")
    except KeyboardInterrupt:
        pass
