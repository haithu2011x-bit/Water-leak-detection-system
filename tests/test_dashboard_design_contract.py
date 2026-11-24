"""Design system regressions: keep all pages consistent and operational.

Static checks do not need a database, Streamlit server or physical sensors.
"""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
PAGES = (
    "overview_page.py",
    "app.py",
    "quality_page.py",
    "experiment_app.py",
    "alerts_app.py",
)


class ProfessionalDashboardContractTests(unittest.TestCase):
    def test_every_page_uses_shared_header(self):
        for filename in PAGES:
            with self.subTest(page=filename):
                source = (DASHBOARD / filename).read_text(encoding="utf-8")
                tree = ast.parse(source)
                headers = [
                    n for n in ast.walk(tree)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == "page_header"
                ]
                self.assertEqual(len(headers), 1)
                self.assertEqual(len(headers[0].args), 2)
                self.assertFalse(headers[0].keywords)
                self.assertIn("apply_theme()", source)

    def test_no_decorative_hero_or_promotional_tags(self):
        ui = (DASHBOARD / "ui.py").read_text(encoding="utf-8")
        nav = (DASHBOARD / "unified_app.py").read_text(encoding="utf-8")
        self.assertNotIn("linear-gradient", ui)
        self.assertNotIn("hero-shell", ui)
        self.assertNotIn("page-kicker-tag", ui)
        self.assertNotIn("WATER INTELLIGENCE", nav)
        self.assertIn("st.navigation(", nav)
        self.assertIn("st.Page(", nav)

    def test_shared_palette_is_defined(self):
        source = (DASHBOARD / "ui.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertTrue(any(
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and (
                any(isinstance(t, ast.Name) and t.id == "FLOW_COLORS" for t in node.targets)
                if isinstance(node, ast.Assign)
                else isinstance(node.target, ast.Name) and node.target.id == "FLOW_COLORS"
            )
            for node in tree.body
        ))
        self.assertIn("RESIDUAL_COLOR", source)

    def test_export_and_state_transitions_remain_available(self):
        experiment = (DASHBOARD / "experiment_app.py").read_text(encoding="utf-8")
        alerts = (DASHBOARD / "alerts_app.py").read_text(encoding="utf-8")
        for term in ("start_session(", "stop_session(", "export_verified_session_csv("):
            self.assertIn(term, experiment)
        self.assertIn("transition(", alerts)
        self.assertIn("get_actions(", alerts)


if __name__ == "__main__":
    unittest.main()
