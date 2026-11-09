"""The import-linter contracts in the root pyproject.toml enforce the context boundaries.

Each test copies the kart package to a temporary directory, writes some imports into it
and runs lint-imports against the real configuration.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# tests/architecture/<this file> -> the repository root.
REPO_ROOT = Path(__file__).resolve().parents[2]
KART_SRC = REPO_ROOT / "src"
LINT_IMPORTS = Path(sys.executable).with_name("lint-imports")
# What the shared kernel and the Core domains must not import.
FRAMEWORKS = ["fastapi", "starlette", "sqlalchemy", "pydantic"]


def contracts_kept(tmp_path: Path, imports: dict[str, str]) -> bool:
    """Write each import line into its module, then report whether every contract is kept."""
    src = tmp_path / "src"
    shutil.copytree(KART_SRC, src, ignore=shutil.ignore_patterns("__pycache__"))
    for module, import_line in imports.items():
        path = src / Path(*module.split("."))
        target = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
        target.write_text(f"{import_line}\n")
    result = subprocess.run(  # noqa: S603 (fixed executable, test-controlled arguments)
        [LINT_IMPORTS, "--config", REPO_ROOT / "pyproject.toml", "--no-cache"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(src)},
        capture_output=True,
        text=True,
        check=False,
    )
    report = result.stdout + result.stderr
    assert "Contracts:" in report, f"lint-imports did not run its contracts:\n{report}"
    return result.returncode == 0


def test_the_boundaries_hold_as_written(tmp_path: Path) -> None:
    assert contracts_kept(tmp_path, {})


def test_a_context_cannot_import_another_contexts_internals(tmp_path: Path) -> None:
    assert not contracts_kept(
        tmp_path, {"kart.contexts.offer": "import kart.contexts.ordering.domain"}
    )


def test_a_context_may_import_another_contexts_contracts(tmp_path: Path) -> None:
    assert contracts_kept(
        tmp_path, {"kart.contexts.offer": "import kart.contexts.ordering.contracts"}
    )


def test_contracts_cannot_expose_their_contexts_internals(tmp_path: Path) -> None:
    assert not contracts_kept(
        tmp_path,
        {
            "kart.contexts.ordering.contracts": "from kart.contexts.ordering.domain import *",
            "kart.contexts.offer": "import kart.contexts.ordering.contracts",
        },
    )


def test_a_context_cannot_import_the_app(tmp_path: Path) -> None:
    assert not contracts_kept(tmp_path, {"kart.contexts.offer": "import kart.app"})


@pytest.mark.parametrize("layer", ["domain", "application", "api", "contracts"])
def test_any_part_of_a_context_may_import_the_shared_kernel(tmp_path: Path, layer: str) -> None:
    assert contracts_kept(
        tmp_path, {f"kart.contexts.ordering.{layer}": "import kart.shared.kernel.money"}
    )


@pytest.mark.parametrize("context", ["ordering", "fulfilment", "offer"])
@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_a_core_domain_imports_no_framework(tmp_path: Path, context: str, framework: str) -> None:
    assert not contracts_kept(tmp_path, {f"kart.contexts.{context}.domain": f"import {framework}"})


def test_a_core_contexts_infrastructure_may_use_a_framework(tmp_path: Path) -> None:
    assert contracts_kept(tmp_path, {"kart.contexts.ordering.infrastructure": "import sqlalchemy"})


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_the_shared_kernel_imports_no_framework(tmp_path: Path, framework: str) -> None:
    assert not contracts_kept(tmp_path, {"kart.shared.kernel.money": f"import {framework}"})


def test_the_shared_kernel_cannot_import_a_context(tmp_path: Path) -> None:
    assert not contracts_kept(
        tmp_path, {"kart.shared.kernel.money": "import kart.contexts.ordering.contracts"}
    )


@pytest.mark.parametrize("layer", ["infrastructure", "migrations"])
def test_a_contexts_adapters_may_use_the_shared_plumbing(tmp_path: Path, layer: str) -> None:
    assert contracts_kept(
        tmp_path, {f"kart.contexts.ordering.{layer}": "import kart.shared.outbox"}
    )


@pytest.mark.parametrize("layer", ["domain", "application", "api", "contracts"])
def test_the_rest_of_a_context_cannot_use_the_shared_plumbing(tmp_path: Path, layer: str) -> None:
    assert not contracts_kept(
        tmp_path, {f"kart.contexts.ordering.{layer}": "import kart.shared.outbox"}
    )


def test_the_shared_plumbing_cannot_import_a_context(tmp_path: Path) -> None:
    assert not contracts_kept(
        tmp_path, {"kart.shared.outbox": "import kart.contexts.ordering.contracts"}
    )


def test_the_shared_kernel_cannot_use_the_shared_plumbing(tmp_path: Path) -> None:
    assert not contracts_kept(tmp_path, {"kart.shared.kernel.money": "import kart.shared.outbox"})


@pytest.mark.parametrize(
    "module", ["kart.app.audiences", "kart.shared.outbox", "kart.contexts.ordering.infrastructure"]
)
def test_only_identity_imports_the_token_library(tmp_path: Path, module: str) -> None:
    assert not contracts_kept(tmp_path, {module: "import jwt"})
