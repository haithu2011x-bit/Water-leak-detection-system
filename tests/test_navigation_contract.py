"""Regression checks for Streamlit navigation (no Streamlit server or DB needed)."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
ROUTER = DASHBOARD / "unified_app.py"


def pages():
    tree = ast.parse(ROUTER.read_text(encoding="utf-8"))
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "Page" and node.args and isinstance(node.args[0], ast.Constant):
            path = node.args[0].value
            options = {
                kw.arg: kw.value.value
                for kw in node.keywords
                if kw.arg and isinstance(kw.value, ast.Constant)
            }
            calls.append((path, options))
    return calls


class NavigationContractTests(unittest.TestCase):
    def test_expected_pages_exist(self):
        registered = pages()
        self.assertEqual(len(registered), 5)
        for name, _ in registered:
            with self.subTest(page=name):
                self.assertTrue((DASHBOARD / name).is_file(), name)

    def test_icons_are_valid_material_shortcodes(self):
        for name, options in pages():
            with self.subTest(page=name):
                self.assertRegex(options.get("icon", ""), r"\A:material/[a-z0-9_]+:\Z")
                self.assertNotIn(":material:", options.get("icon", ""))

    def test_only_one_default(self):
        self.assertEqual(sum(opts.get("default") is True for _, opts in pages()), 1)

    def test_expected_modules(self):
        self.assertTrue((ROOT / "tools" / "unified_dashboard_service.py").is_file())
        self.assertTrue((ROOT / "tools" / "alert_service.py").is_file())
        self.assertTrue((ROOT / "tools" / "experiment_service.py").is_file())

    def test_streamlit_minimum_version(self):
        content = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("streamlit>=1.46,<2", content)

if __name__ == "__main__":
    unittest.main()
