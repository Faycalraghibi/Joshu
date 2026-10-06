"""The project map in the system prompt."""

from joshu.core import repo_map
from joshu.core.repo_map import build_repo_map, definitions


def write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_definitions_by_language(tmp_path):
    write(
        tmp_path,
        {
            "a.py": "import os\nX = 1\nclass Shop:\n    def __init__(self): ...\n"
            "    def total(self): ...\n    def _hidden(self): ...\nasync def fetch(): ...\n",
            "b.ts": "export function load() {}\nexport class Store {}\n"
            "export const save = async (x) => x\nexport interface Item {}\n",
            "c.go": "package x\nfunc (s *Shop) Total() int {}\nfunc main() {}\ntype Shop struct{}\n",
            "broken.py": "def (:\n",
        },
    )
    assert definitions(tmp_path / "a.py") == ["Shop(__init__, total)", "fetch"]
    assert definitions(tmp_path / "b.ts") == ["load", "Store", "save", "Item"]
    assert definitions(tmp_path / "c.go") == ["Total", "main", "Shop"]
    assert definitions(tmp_path / "broken.py") == []


def test_map_groups_files_by_directory_and_skips_noise(tmp_path):
    tmp_path = tmp_path / "project"  # the test home's config.yaml is in tmp_path
    write(
        tmp_path,
        {
            "README.md": "x",
            "app/models.py": "class User: ...\n",
            "app/api/routes.py": "def index(): ...\n",
            "node_modules/lib/index.js": "function x() {}\n",
            "app/__pycache__/models.cpython-313.pyc": "",
            ".env": "SECRET=1",
        },
    )
    text = build_repo_map(tmp_path)
    assert text.splitlines()[1:] == [
        "README.md",
        "app/",
        "  models.py: User",
        "app/api/",
        "  routes.py: index",
    ]
    assert build_repo_map(tmp_path, "never") is None


def test_big_projects(tmp_path, monkeypatch):
    write(tmp_path, {f"pkg/mod{i}.py": f"def function_number_{i}(): ...\n" for i in range(30)})
    # Over the size: auto keeps the layout without definitions, always cuts
    assert "function_number" not in build_repo_map(tmp_path, max_chars=400)
    assert build_repo_map(tmp_path, max_chars=100) is None
    cut = build_repo_map(tmp_path, "always", max_chars=200)
    assert cut is not None and "more lines" in cut
    monkeypatch.setattr(repo_map, "MAX_FILES", 10)
    assert build_repo_map(tmp_path) is None
    assert build_repo_map(tmp_path, "always") is not None


def test_definitions_are_cached_until_the_file_changes(tmp_path):
    path = tmp_path / "m.py"
    path.write_text("def one(): ...\n", encoding="utf-8")
    assert definitions(path) == ["one"]
    path.write_text("def one(): ...\ndef two(): ...\n", encoding="utf-8")
    assert definitions(path) == ["one", "two"]


def test_agent_puts_the_map_in_its_system_prompt(tmp_path):
    from joshu.core.agent import Agent
    from joshu.core.config import get_config_manager
    from joshu.core.permissions import PermissionManager, PermissionMode

    write(tmp_path, {"shop.py": "def checkout(): ...\n"})

    class Client:
        model = "fake"

    def prompt():
        agent = Agent(
            client=Client(), permissions=PermissionManager(PermissionMode.DEFAULT), cwd=tmp_path
        )
        return agent.messages[0]["content"]

    assert "shop.py: checkout" in prompt()
    get_config_manager().set("repo_map", "never")
    assert "Project map" not in prompt()
