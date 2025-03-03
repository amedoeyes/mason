from setuptools import setup

setup(
    name="mason",
    version="1.0.0",
    install_requires=["jinja2", "requests", "tqdm", "argcomplete"],
    entry_points={"console_scripts": ["mason=mason.cli:main"]},
    python_requires=">=3.13",
)
