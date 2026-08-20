import tomllib
from pathlib import Path

import adclip


def test_package_version_matches_pyproject_and_mcp_major_is_bounded():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    assert project["version"] == adclip.__version__ == "0.2.0"

    dependencies = project["dependencies"]
    mcp = next(item for item in dependencies if item.startswith("mcp"))
    assert ">=1.2.0" in mcp
    assert "<2" in mcp
    assert pyproject["project"]["scripts"]["adclip"] == "adclip.entry:main"
