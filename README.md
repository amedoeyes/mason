# Mason

A fast and efficient command-line tool to manage external development tools like LSP servers, debuggers, linters, and formatters.

![demo](https://github.com/user-attachments/assets/2c9aab56-edaa-4972-b24d-24c3a722c844)

## Building

```sh
git clone https://github.com/amedoeyes/mason.git
cd mason
go build -o mason .
```

## Usage

Add `$HOME/.local/share/mason/bin` to your PATH if you're on Unix, or `%APPDATA%\mason\bin` if you're on Windows. This ensures installed binaries are accessible from anywhere.

```
Usage:
  mason [command]

Available Commands:
  completion  Generate the autocompletion script for the specified shell
  help        Help about any command
  install     Install packages
  list        List installed packages
  search      Search packages
  uninstall   Uninstall packages
  update      Update repositories
  upgrade     Upgrade packages

Flags:
  -h, --help   help for mason

Use "mason [command] --help" for more information about a command.
```

## Environment Variables

- MASON_DATA_DIR: Base directory for data (defaults to `$HOME/.local/share/mason` on Unix and `%APPDATA%\mason` on Windows).
- MASON_REGISTRIES: Comma-separated list of registries (defaults to `github:mason-org/mason-registry`).

## Credits

This project is inspired by and named after [mason.nvim](https://github.com/williamboman/mason.nvim), the popular Neovim plugin for managing LSPs, DAPs, linters, and formatters. This project extends that philosophy to the command line, making external tooling management more accessible outside of Neovim.

## Contributing

Contributions are welcome! If you notice a bug or want to add a feature, feel free to open an issue or submit a pull request.
