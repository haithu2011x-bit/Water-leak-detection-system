"""Pure presentation filters for unverified telemetry and MQTT quality logs.

These helpers do not modify SQLite data, provenance labels, or AI decisions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FLOW_COLUMNS = ("flow_main", "flow_z1", "flow_z2")


def prepare_telemetry_history(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep measurements with a UTC timestamp and finite, nonnegative flows."""
    data = frame.copy()
    data["ts_server"] = pd.to_datetime(data["ts_server"], utc=True, errors="coerce")
    valid = data["ts_server"].notna()
    for channel in FLOW_COLUMNS:
        data[channel] = pd.to_numeric(data[channel], errors="coerce")
        valid &= np.isfinite(data[channel]) & data[channel].ge(0)
    data = data.loc[valid].copy()
    data["residual"] = data["flow_main"] - data["flow_z1"] - data["flow_z2"]
    return data


def filter_telemetry_dates(frame: pd.DataFrame, selected_range) -> pd.DataFrame:
    """Only apply an inclusive UTC date filter when both dates are selected."""
    if not isinstance(selected_range, (tuple, list)) or len(selected_range) != 2:
        return frame.copy()
    start, end = selected_range
    return frame.loc[
        frame["ts_server"].dt.date.ge(start) & frame["ts_server"].dt.date.le(end)
    ].copy()


def filter_quality_log(frame: pd.DataFrame, selected_kinds, query: str) -> pd.DataFrame:
    """Search literal text, including characters that are special in regex."""
    kinds = (frame["kind"].fillna("unknown").astype(str) if "kind" in frame
             else pd.Series("unknown", index=frame.index))
    filtered = frame.loc[kinds.isin(selected_kinds)].copy()
    term = query.strip()
    if term:
        matches = filtered.astype(str).apply(
            lambda column: column.str.contains(term, case=False, na=False, regex=False)
        ).any(axis=1)
        filtered = filtered.loc[matches].copy()
    return filtered
