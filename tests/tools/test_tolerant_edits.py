"""Edits whose old_string is off only by whitespace still apply, when unambiguous."""

import json

from joshu.tools import filesystem_tools
from joshu.tools.edit_tools import apply_edits
from joshu.tools.filesystem_tools import replace_tool, tolerant_replace

CODE = "class Cart:\n    def total(self):\n        return sum(self.items)\n\n    def size(self):\n        return len(self.items)\n"


def test_indentation_off_by_the_same_amount():
    # The model dropped the class indentation from both old and new
    old = "def total(self):\n    return sum(self.items)"
    new = "def total(self):\n    return round(sum(self.items), 2)"
    content, first, last = tolerant_replace(CODE, old, new)
    assert "        return round(sum(self.items), 2)\n" in content
    assert "    def total(self):\n" in content and (first, last) == (2, 3)
    assert content.endswith("        return len(self.items)\n")


def test_trailing_spaces_and_extra_indentation():
    old = "            return len(self.items)   "  # too deep and trailing spaces
    content, _, _ = tolerant_replace(CODE, old, "            return 0")
    assert "        return 0\n" in content


def test_ambiguous_or_inconsistent_matches_are_refused():
    twice = "def a():\n    pass\n\ndef b():\n    pass\n"
    assert tolerant_replace(twice, "  pass", "  return") is None
    # Lines match when stripped, but the indentation change differs between them
    assert tolerant_replace(CODE, "def total(self):\nreturn sum(self.items)", "x") is None
    assert tolerant_replace(CODE, "not there", "x") is None
    assert tolerant_replace(CODE, "   \n", "x") is None


def test_crlf_files_keep_their_line_endings():
    crlf = CODE.replace("\n", "\r\n")
    content, _, _ = tolerant_replace(crlf, "return len(self.items)", "return 0")
    assert "        return 0\r\n" in content and "\n" not in content.replace("\r\n", "")


def test_replace_tool_uses_it_and_says_so(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    try:
        (tmp_path / "cart.py").write_text(CODE, encoding="utf-8")
        result = replace_tool("cart.py", "return len(self.items)  ", "return 0")
        assert result["success"] and "indentation" in result["note"]
        assert "+        return 0" in result["diff"]
        assert "        return 0\n" in (tmp_path / "cart.py").read_text(encoding="utf-8")
        missing = replace_tool("cart.py", "return nothing", "x")
        assert not missing["success"]
        json.dumps(result)
    finally:
        filesystem_tools._workspace_root = None


def test_multi_edit_uses_it():
    out = apply_edits(CODE, [{"old_string": "return len(self.items)", "new_string": "return 0"}])
    assert "return 0" in out  # exact match: unchanged behaviour
    out = apply_edits(
        CODE,
        [
            {
                "old_string": "def size(self):\n    return len(self.items)",
                "new_string": "def size(self):\n    return 0",
            }
        ],
    )
    assert "    def size(self):\n        return 0\n" in out
