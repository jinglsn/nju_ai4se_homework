from setuptools import setup, find_packages

setup(
    name="harness",
    version="0.1.0",
    packages=find_packages(include=["src", "src.*"]),
    install_requires=[
        "pytest>=8.0",
        "fastapi>=0.115",
        "uvicorn>=0.30",
        "keyring>=25.0",
    ],
    entry_points={
        "console_scripts": [
            "harness=src.cli:main",
        ],
    },
)