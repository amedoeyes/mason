from setuptools import setup

setup(
    name="mason",
    version="1.0.0",
    install_requires=["argcomplete", "jinja2", "portalocker", "pyyaml", "requests", "tqdm"],
    entry_points={"console_scripts": ["mason=mason.cli:main"]},
)
