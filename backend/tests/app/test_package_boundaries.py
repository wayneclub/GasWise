"""Prevent HTTP and application dependencies from leaking into core packages."""

import ast
import importlib.util
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "gaswise"


@pytest.mark.parametrize(
    "layer, forbidden",
    [
        ("contracts", ("gaswise.api", "gaswise.app", "gaswise.services", "gaswise.providers")),
        ("domain", ("gaswise.api", "gaswise.app", "gaswise.services", "gaswise.providers")),
        ("providers", ("gaswise.api", "gaswise.app", "gaswise.services")),
        ("services", ("gaswise.api", "gaswise.app")),
    ],
)
def test_dependency_direction(layer, forbidden):
    violations = []
    for path in (PACKAGE / layer).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            elif isinstance(node, ast.Import):
                modules = [item.name for item in node.names]
            else:
                continue
            for module in modules:
                if any(module == prefix or module.startswith(prefix + ".") for prefix in forbidden):
                    violations.append(f"{path.relative_to(PACKAGE)}:{node.lineno}: {module}")
    assert not violations, "Invalid dependency direction:\n" + "\n".join(violations)


def test_project_module_imports_resolve_after_relocation():
    missing = []
    for path in PACKAGE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            elif isinstance(node, ast.Import):
                modules = [item.name for item in node.names]
            else:
                continue
            for module in modules:
                if module.startswith("gaswise.") and importlib.util.find_spec(module) is None:
                    missing.append(f"{path.relative_to(PACKAGE)}:{node.lineno}: {module}")
    assert not missing, "Missing project imports:\n" + "\n".join(missing)
