import os
from pathlib import Path

from mason.utility import select_by_os

default_cache_dir = select_by_os(
    unix=Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")) / "mason",
    windows=Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData/Local")) / "mason",
)
default_data_dir = select_by_os(
    unix=Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share")) / "mason",
    windows=Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming")) / "mason",
)

registry_repo = os.getenv("MASON_REGISTRY_REPO", "mason-org/mason-registry")
cache_dir = Path(os.getenv("MASON_CACHE_DIR", default_cache_dir)).expanduser()
data_dir = Path(os.getenv("MASON_DATA_DIR", default_data_dir)).expanduser()

bin_dir = data_dir / "bin"
share_dir = data_dir / "share"
opt_dir = data_dir / "opt"
packages_dir = data_dir / "packages"
registry_path = cache_dir / "registry.json"
