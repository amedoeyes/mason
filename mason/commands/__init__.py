import pkgutil
import importlib

for _, module_name, _ in pkgutil.iter_modules(__path__):
    globals()[module_name] = getattr(importlib.import_module(f".{module_name}", __name__), module_name)
