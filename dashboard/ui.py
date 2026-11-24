"""Shared, restrained visual language for the Project II monitoring dashboard.

Prefer native Streamlit widgets and accessible, meaningful status text.
Only use HTML for layout details that Streamlit does not expose directly.
"""
from __future__ import annotations

from html import escape

import streamlit as st

# Consistent across overview, history, experiments and quality plots.
FLOW_COLORS = ("#167a78", "#4779a8", "#b88246")
RESIDUAL_COLOR = "#786c87"

CSS = """
<style>
:root {
  --surface: #ffffff;
  --canvas: #f7f9fa;
  --sidebar: #eef2f3;
  --ink: #1f2d35;
  --muted: #586a73;
  --line: #dce4e7;
  --accent: #166e71;
}
[data-testid="stAppViewContainer"] {
  background: var(--canvas);
  color: var(--ink);
}
[data-testid="stHeader"] { background: rgba(247, 249, 250, .96); }
.block-container { max-width: 1280px; padding-top: 1.6rem; padding-bottom: 3rem; }
[data-testid="stSidebar"] {
  background: var(--sidebar);
  border-right: 1px solid var(--line);
}
[data-testid="stSidebarNav"] { padding-top: .25rem; }
[data-testid="stSidebarNav"] a {
  border-radius: 6px;
  margin: 2px 8px;
  color: var(--ink);
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
  background: #dcebec;
  color: #115e63;
  font-weight: 650;
}
[data-testid="stHeading"] h1 {
  color: var(--ink);
  font-size: clamp(1.65rem, 2.8vw, 2.1rem);
  font-weight: 680;
  letter-spacing: -.025em;
  line-height: 1.25;
}
h2, h3 { color: var(--ink); }
[data-testid="stMetric"] {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  padding: 14px 16px;
  box-shadow: none;
}
[data-testid="stMetricLabel"] { color: var(--muted); font-size: .83rem; }
[data-testid="stMetricValue"] { color: var(--ink); font-weight: 650; }
div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button,
div[data-testid="stFormSubmitButton"] > button {
  border-radius: 6px;
  border: 1px solid #cbd7db;
  min-height: 2.45rem;
  box-shadow: none;
  font-weight: 550;
}
div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
[data-testid="stTabs"] button { font-weight: 550; }
[data-testid="stDataFrame"],
[data-testid="stTable"],
[data-testid="stExpander"],
[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: 8px;
  border-color: var(--line);
  box-shadow: none;
}
[data-testid="stAlert"] { border-radius: 6px; }
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div, textarea {
  border-radius: 6px !important;
}
.page-rule {
  border-bottom: 1px solid var(--line);
  margin: 1rem 0 1.25rem;
}
.section-heading {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  column-gap: .85rem;
  row-gap: .25rem;
  border-bottom: 1px solid var(--line);
  padding-bottom: .5rem;
  margin: 1.75rem 0 .85rem;
}
.section-heading h2 {
  margin: 0;
  font-size: 1.08rem;
  font-weight: 650;
  line-height: 1.4;
  letter-spacing: -.01em;
}
.section-heading p {
  margin: 0;
  color: var(--muted);
  font-size: .83rem;
  line-height: 1.5;
}
.empty-state {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 1.25rem 1.4rem;
}
.empty-state strong {
  display: block;
  color: var(--ink);
  margin-bottom: .25rem;
  font-weight: 650;
}
.empty-state p { color: var(--muted); margin: 0; font-size: .88rem; }
.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: .5rem;
  font-size: .9rem;
  font-weight: 600;
  color: var(--ink);
}
.status-indicator::before {
  content: "";
  width: .48rem;
  height: .48rem;
  border-radius: 50%;
  flex-shrink: 0;
  background: #87969d;
}
.status-good::before { background: #247b59; }
.status-warn::before { background: #b17d25; }
.status-bad::before { background: #b34949; }
@media (max-width: 768px) {
  .block-container { padding: 1.15rem .85rem 2rem; }
  .section-heading { margin-top: 1.3rem; }
}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str) -> None:
    """One consistent title and short descriptive line on every page."""
    st.title(title)
    st.caption(subtitle)
    st.markdown('<div class="page-rule"></div>', unsafe_allow_html=True)


def section_title(title: str, detail: str | None = None) -> None:
    detail_html = f"<p>{escape(detail)}</p>" if detail else ""
    st.markdown(
        f'<div class="section-heading"><h2>{escape(title)}</h2>{detail_html}</div>',
        unsafe_allow_html=True,
    )


def empty_state(title: str, message: str) -> None:
    st.markdown(
        f'<div class="empty-state"><strong>{escape(title)}</strong>'
        f'<p>{escape(message)}</p></div>',
        unsafe_allow_html=True,
    )


def status_chip(label: str, kind: str = "neutral") -> None:
    """A colored dot only for an operational status, not decorative badges."""
    css = kind if kind in {"good", "warn", "bad"} else "neutral"
    st.markdown(
        f'<span class="status-indicator status-{css}">{escape(label)}</span>',
        unsafe_allow_html=True,
    )
