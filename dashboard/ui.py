"""Shared visual system for the Project II Streamlit dashboard."""
from __future__ import annotations

from html import escape

import streamlit as st


CSS = """
<style>
:root {
  --ink: #17243b;
  --muted: #68778f;
  --line: #e5ebf3;
  --surface: #ffffff;
  --canvas: #f3f6fb;
  --navy: #10233f;
  --blue: #2868d7;
  --cyan: #18a6b8;
}
[data-testid="stAppViewContainer"] { background: var(--canvas); color: var(--ink); }
[data-testid="stHeader"] { background: rgba(243,246,251,.88); }
.block-container { max-width: 1500px; padding-top: 1.7rem; padding-bottom: 3rem; }
h1,h2,h3 { color: var(--ink); letter-spacing: -.025em; }
p, label, [data-testid="stMarkdownContainer"] { color: inherit; }
[data-testid="stSidebar"] { background: #10233f; border-right: 1px solid #203b5e; }
[data-testid="stSidebar"] * { color: #e7eef9; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #b8c8dd; }
[data-testid="stSidebar"] hr { border-color: #2a4262; }
[data-testid="stSidebarNav"] { padding-top: .4rem; }
[data-testid="stSidebarNav"] a { border-radius: 10px; margin: 3px 7px; }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: #24466f; }
[data-testid="stMetric"] {
  background: #fff; border: 1px solid var(--line); border-radius: 15px;
  padding: 15px 17px; box-shadow: 0 3px 12px rgba(20,45,80,.035);
}
[data-testid="stMetricLabel"] { color: #64748b; font-size: .83rem; }
[data-testid="stMetricValue"] { color: var(--ink); font-weight: 750; }
div[data-testid="stButton"] > button, div[data-testid="stDownloadButton"] > button,
div[data-testid="stFormSubmitButton"] > button {
  border-radius: 10px; font-weight: 650; min-height: 2.55rem;
  border: 1px solid #d9e2ee; transition: all .15s ease;
}
div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
  background: #2868d7; border-color: #2868d7; color: #fff;
}
div[data-testid="stButton"] > button:hover, div[data-testid="stDownloadButton"] > button:hover {
  border-color: #2868d7; color: #2058b8;
}
[data-testid="stTabs"] button { font-weight: 650; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
[data-testid="stAlert"] { border-radius: 12px; }
[data-testid="stExpander"] { background: #fff; border: 1px solid var(--line); border-radius: 12px; }
[data-testid="stVerticalBlockBorderWrapper"] { background: #fff; border-color: var(--line); border-radius: 16px; }
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, textarea {
  border-radius: 10px !important;
}
.hero-shell {
  position: relative; overflow: hidden; border-radius: 22px; padding: 27px 30px;
  margin: 0 0 22px; color: #fff;
  background: linear-gradient(115deg, #102947 0%, #174d7b 57%, #207f99 100%);
  box-shadow: 0 12px 28px rgba(18,53,88,.13);
}
.hero-shell:after {
  content: ""; position: absolute; width: 280px; height: 280px; border-radius: 50%;
  right: -65px; top: -145px; border: 1px solid rgba(255,255,255,.18);
  box-shadow: 0 0 0 28px rgba(255,255,255,.035), 0 0 0 58px rgba(255,255,255,.025);
}
.hero-eyebrow { color: #a9d9ea !important; text-transform: uppercase; letter-spacing: .14em;
  font-size: .72rem; font-weight: 750; margin: 0 0 9px; }
.hero-title { color: #fff !important; font-size: clamp(1.65rem, 3vw, 2.35rem);
  font-weight: 780; letter-spacing: -.04em; line-height: 1.12; margin: 0 0 9px; }
.hero-subtitle { color: #d4e7f4 !important; max-width: 850px; font-size: .96rem; margin: 0; line-height: 1.55; }
.hero-tag { display: inline-block; margin-top: 17px; background: rgba(255,255,255,.13);
  border: 1px solid rgba(255,255,255,.22); padding: 5px 10px; border-radius: 99px;
  color: #f4fbff !important; font-size: .75rem; font-weight: 650; }
.section-heading { display: flex; align-items: baseline; gap: 10px; margin: 1.25rem 0 .65rem; }
.section-heading h3 { font-size: 1.12rem; font-weight: 750; margin: 0; }
.section-heading span { color: var(--muted); font-size: .82rem; }
.soft-note { background: #edf5ff; border: 1px solid #d9e9fc; color: #355678;
  border-radius: 12px; padding: 12px 15px; font-size: .88rem; line-height: 1.5; }
.status-chip { display: inline-block; border-radius: 99px; padding: 5px 10px; font-size: .76rem; font-weight: 700; }
.status-good { color: #176b48; background: #e4f6ed; }
.status-warn { color: #8a5a12; background: #fff2d9; }
.status-bad { color: #9b3434; background: #fdeaea; }
.status-neutral { color: #52647c; background: #edf1f6; }
.empty-state { background: #fff; border: 1px dashed #cbd7e5; border-radius: 16px;
  padding: 25px; text-align: center; color: #64748b; }
.empty-state strong { display:block; color: #243650; font-size: 1rem; margin-bottom: 5px; }
.small-muted { color: #718096; font-size: .8rem; }
div[data-testid="stPlotlyChart"], div[data-testid="stVegaLiteChart"], div[data-testid="stArrowVegaLiteChart"] {
  background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 8px;
}
@media (max-width: 700px) {
  .block-container { padding: 1rem .8rem 2rem; }
  .hero-shell { padding: 22px 20px; border-radius: 16px; }
}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str, eyebrow: str = "PROJECT II · WATER INTELLIGENCE",
                tag: str | None = None) -> None:
    tag_html = f'<div class="hero-tag">{escape(tag)}</div>' if tag else ""
    st.markdown(
        f'<section class="hero-shell"><div class="hero-eyebrow">{escape(eyebrow)}</div>'
        f'<h1 class="hero-title">{escape(title)}</h1>'
        f'<p class="hero-subtitle">{escape(subtitle)}</p>{tag_html}</section>',
        unsafe_allow_html=True,
    )


def section_title(title: str, detail: str | None = None) -> None:
    detail_html = f"<span>{escape(detail)}</span>" if detail else ""
    st.markdown(
        f'<div class="section-heading"><h3>{escape(title)}</h3>{detail_html}</div>',
        unsafe_allow_html=True,
    )


def empty_state(title: str, message: str) -> None:
    st.markdown(
        f'<div class="empty-state"><strong>{escape(title)}</strong>{escape(message)}</div>',
        unsafe_allow_html=True,
    )


def status_chip(label: str, kind: str = "neutral") -> None:
    allowed = {"good": "status-good", "warn": "status-warn", "bad": "status-bad"}
    css = allowed.get(kind, "status-neutral")
    st.markdown(f'<span class="status-chip {css}">{escape(label)}</span>', unsafe_allow_html=True)
