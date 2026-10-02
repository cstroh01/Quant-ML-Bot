"""Project root by marker, never by depth and never by working directory.

Contract (spec 043 FR-006, identical to spec 040 §1.5 R1):

1. If ``QMB_PROJECT_ROOT`` is set (even to an empty string), it must be an
   absolute path to a directory containing the marker, or
   ``ProjectRootNotFound`` is raised naming it.
2. Otherwise the root is the nearest ancestor of this module's resolved
   ``__file__`` that contains the marker.
3. Otherwise ``ProjectRootNotFound`` is raised, naming every place searched.

The marker is a ``pyproject.toml`` whose ``[project] name`` is
``quant-ml-bot``, read with stdlib ``tomllib``. The current working directory
is never consulted: with two clones, a cwd lookup would silently pair one
clone's code with the other clone's ledger. Nothing is cached, so a changed
environment is seen on the next call.
"""
from __future__ import annotations

import os
from pathlib import Path
import tomllib

PROJECT_NAME = "quant-ml-bot"
OVERRIDE_VAR = "QMB_PROJECT_ROOT"


class ProjectRootNotFound(RuntimeError):
    """No directory carrying the quant-ml-bot marker was found where searched."""


def is_project_root(directory: Path) -> bool:
    """True only if ``directory/pyproject.toml`` parses and names this project."""
    path = directory / "pyproject.toml"
    if not path.is_file():
        return False
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    project = data.get("project")
    return isinstance(project, dict) and project.get("name") == PROJECT_NAME


def project_root() -> Path:
    """Return the resolved project root, or raise naming where it looked."""
    override = os.environ.get(OVERRIDE_VAR)
    if override is not None:
        # Set means validated: an empty or relative value would be read against
        # the working directory (or ignored), which this contract never consults.
        if not override or not Path(override).is_absolute():
            raise ProjectRootNotFound(
                f"{OVERRIDE_VAR}={override!r} must be an absolute path to a "
                f"directory whose pyproject.toml has [project] name = {PROJECT_NAME!r}"
            )
        root = Path(override).resolve()
        if is_project_root(root):
            return root
        raise ProjectRootNotFound(
            f"{OVERRIDE_VAR}={root} has no pyproject.toml with "
            f"[project] name = {PROJECT_NAME!r}"
        )
    start = Path(__file__).resolve().parent
    searched = [start, *start.parents]
    for directory in searched:
        if is_project_root(directory):
            return directory
    raise ProjectRootNotFound(
        f"no pyproject.toml with [project] name = {PROJECT_NAME!r}; "
        f"{OVERRIDE_VAR} is unset and the ancestors of {start} were searched: "
        + ", ".join(str(directory) for directory in searched)
    )
