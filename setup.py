"""Minimal setup.py for pip install -e . support."""

from setuptools import setup, find_packages

setup(
    name="fuel_analysis",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "pandas>=2.0,<3.0",
        "matplotlib>=3.7,<4.0",
        "pydantic>=2.0,<3.0",
    ],
)
