"""Streamlit execution smoke checks, including real st.Page/st.navigation validation.

Both pages exercised are read-only. No fake data or AI is generated.
Requires Streamlit 1.61+ for reliable multipage AppTest support.
"""
import unittest
from importlib.metadata import version
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "dashboard" / "unified_app.py"


def supports_navigation_test():
    if AppTest is None:
        return False
    major_minor = tuple(int(x) for x in version("streamlit").split(".")[:2])
    return major_minor >= (1, 61)


@unittest.skipUnless(supports_navigation_test(), "Multipage AppTest requires Streamlit >= 1.61")
class StreamlitNavigationSmokeTests(unittest.TestCase):
    def test_default_overview_loads_without_exception(self):
        at = AppTest.from_file(str(ENTRY), default_timeout=20).run()
        self.assertFalse(list(at.exception), [x.message for x in at.exception])
        self.assertTrue(any("Tổng quan" in x.value for x in at.title))

    def test_quality_page_loads_without_exception(self):
        at = AppTest.from_file(str(ENTRY), default_timeout=20).run()
        self.assertFalse(list(at.exception), [x.message for x in at.exception])
        at.switch_page("quality_page.py").run()
        self.assertFalse(list(at.exception), [x.message for x in at.exception])
        self.assertTrue(any("Chất lượng" in x.value for x in at.title))


if __name__ == "__main__":
    unittest.main()
