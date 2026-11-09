"""Generate minimum dependency requirements for supported Python versions.

Dependencies are read from PEP 621 project metadata rather than Poetry configuration.
Python 3.14 is the minimum supported version of NOMAD CAMELS.
"""

from pathlib import Path
import tomllib

from packaging.requirements import Requirement
from packaging.version import Version

OUTPUT_DIR = Path(__file__).resolve().parent


def _extract_versions(pyproject_path, python_versions, lower_bound):
    with open(pyproject_path, "rb") as handle:
        project = tomllib.load(handle)["project"]
    results = {version: {} for version in python_versions}
    for text in project["dependencies"]:
        requirement = Requirement(text)
        for python_version in python_versions:
            if requirement.marker and not requirement.marker.evaluate(
                {"python_version": python_version}
            ):
                continue
            operators = {">=", ">", "=="} if lower_bound else {"<", "<=", "=="}
            candidates = [
                Version(spec.version)
                for spec in requirement.specifier
                if spec.operator in operators
            ]
            if not candidates:
                continue
            version = max(candidates) if lower_bound else min(candidates)
            previous = results[python_version].get(requirement.name)
            if previous is None or (
                (lower_bound and Version(previous) < version)
                or (not lower_bound and Version(previous) > version)
            ):
                results[python_version][requirement.name] = str(version)
    return results


def extract_min_versions(pyproject_path="pyproject.toml", python_versions=None):
    """Return minimum declared versions for Python 3.14 by default."""
    return _extract_versions(pyproject_path, python_versions or ["3.14"], True)


def extract_max_versions(pyproject_path="pyproject.toml", python_versions=None):
    """Return maximum declared bounds for Python 3.14 by default."""
    return _extract_versions(pyproject_path, python_versions or ["3.14"], False)


def print_requirements_txt(min_versions_by_python):
    """Write requirement pins for optional minimum-version testing."""
    for python_version, minimums in min_versions_by_python.items():
        path = OUTPUT_DIR / f"req_min_{python_version}.txt"
        with path.open("w", encoding="utf-8") as handle:
            for package, version in sorted(minimums.items()):
                handle.write(f"{package}=={version}\n")
                print(f"{package}=={version}")


if __name__ == "__main__":
    print_requirements_txt(extract_min_versions())
