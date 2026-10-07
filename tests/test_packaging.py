import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_requirements_txt_mirrors_pyproject_dependencies():
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    listed = [line.strip() for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
              if line.strip() and not line.startswith("#")]
    assert sorted(listed) == sorted(declared)
