"""Project and asset locations for the Back font build."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
ASSETS = PROJECT_ROOT / "assets"
INPUT = ASSETS / "inputs"
LICENSES = ASSETS / "licenses"
ZERO = ASSETS / "zero"
CONFIG = PROJECT_ROOT / "config.toml"
DIST = PROJECT_ROOT / "dist"
SOURCES = ASSETS / "sources.toml"
