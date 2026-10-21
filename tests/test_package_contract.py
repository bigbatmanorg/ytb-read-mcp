import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_installable_project_metadata_and_docs():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert meta["project"]["name"] == "ytb-read-mcp"
    assert meta["project"]["scripts"]["ytb-read-mcp"].endswith("cli:main")
    assert any(dep.startswith("deno") for dep in meta["project"]["dependencies"])
    for path in (
        "README.md",
        "LICENSE",
        "Dockerfile",
        "compose.yaml",
        "docs/installation.md",
        "docs/tools.md",
        "docs/configuration.md",
        "docs/architecture.md",
        "docs/testing.md",
        ".github/workflows/tests.yml",
    ):
        assert (ROOT / path).is_file(), path


def test_mcp_registration_names_and_docstrings():
    source = (ROOT / "src/youtube_read_mcp/server.py").read_text()
    tree = ast.parse(source)
    items = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("youtube_"):
            assert len(ast.get_docstring(node) or "") >= 65, node.name
            assert node.returns is not None, node.name
            items.append(node.name)
    assert len(items) == 26
    assert len(set(items)) == len(items)
