from setuptools import setup, find_packages

setup(
    name="harness-web-agent",
    version="0.1.0",
    packages=find_packages(include=["src", "src.*", "web", "web.*"]),
    install_requires=[
        "pytest>=8.0",
        "fastapi>=0.115",
        "uvicorn>=0.30",
        "httpx>=0.27",
    ],
)