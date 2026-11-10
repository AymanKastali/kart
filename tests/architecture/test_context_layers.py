"""A context's code sits only in the classic layers, beside its contracts and migrations."""

from pathlib import Path

import pytest

# tests/architecture/<this file> -> the repository root.
CONTEXTS = Path(__file__).resolve().parents[2] / "src" / "kart" / "contexts"
LAYERS = {"domain", "application", "infrastructure", "presentation"}
CONTEXT_SURFACES = {"contracts", "migrations"}


def top_level_parts(context: Path) -> set[str]:
    """The names of a context's top-level packages and modules."""
    packages = {path.name for path in context.iterdir() if (path / "__init__.py").is_file()}
    modules = {path.stem for path in context.glob("*.py") if path.name != "__init__.py"}
    return packages | modules


@pytest.mark.parametrize(
    "context",
    sorted(path for path in CONTEXTS.iterdir() if (path / "__init__.py").is_file()),
    ids=lambda context: context.name,
)
def test_a_context_holds_only_its_layers_contracts_and_migrations(context: Path) -> None:
    assert top_level_parts(context) <= LAYERS | CONTEXT_SURFACES
