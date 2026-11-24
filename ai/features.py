import numpy as np
import pandas as pd

WINDOW = 10
FEATURES = [
    "flow_main", "flow_z1", "flow_z2",
    "balance_residual", "flow_mean_10", "flow_std_10",
    "z1_mean_10", "z2_mean_10",
    "z1_share", "z2_share", "flow_delta", "continuous_flow_sec",
]


def _continuous_flow(values: pd.Series, threshold: float = 0.10) -> pd.Series:
    """Dem so mau lien tiep co luu luong; gioi han 120 mau de tranh troi thang."""
    count = 0
    result = []
    for flow in values:
        count = min(120, count + 1) if flow > threshold else 0
        result.append(count)
    return pd.Series(result, index=values.index, dtype=float)


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """Nhan DataFrame telemetry, tra ve cac mau du 10 moc du lieu.

    Khong noi rolling window qua khoang mat mau (gap >5 giay / ID bi gian doan).
    Loai hang co du lieu flow loi/thieu, khong tu bien gia tri thieu thanh 0.
    """
    required = {"id", "ts_server", "flow_main", "flow_z1", "flow_z2"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Telemetry thieu cot: {sorted(missing)}")
    if df.empty:
        return pd.DataFrame(columns=[*df.columns, *FEATURES])

    d = df.copy().sort_values("id").reset_index(drop=True)
    for col in ("flow_main", "flow_z1", "flow_z2"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["flow_main", "flow_z1", "flow_z2"])
    for col in ("flow_main", "flow_z1", "flow_z2"):
        d = d[np.isfinite(d[col]) & (d[col] >= 0)]
    d = d.reset_index(drop=True)
    if d.empty:
        return pd.DataFrame(columns=[*df.columns, *FEATURES])

    timestamp = pd.to_datetime(d["ts_server"], errors="coerce", utc=True)
    seconds = timestamp.diff().dt.total_seconds()
    id_gap = d["id"].diff().ne(1)
    discontinuity = id_gap | seconds.gt(5) | seconds.lt(0) | timestamp.isna()
    d["_run"] = discontinuity.cumsum()
    grp = d.groupby("_run", sort=False)["flow_main"]

    d["balance_residual"] = d["flow_main"] - d["flow_z1"] - d["flow_z2"]
    d["flow_mean_10"] = grp.transform(lambda s: s.rolling(WINDOW, min_periods=WINDOW).mean())
    d["flow_std_10"] = grp.transform(lambda s: s.rolling(WINDOW, min_periods=WINDOW).std(ddof=0))
    d["z1_mean_10"] = d.groupby("_run", sort=False)["flow_z1"].transform(
        lambda s: s.rolling(WINDOW, min_periods=WINDOW).mean()
    )
    d["z2_mean_10"] = d.groupby("_run", sort=False)["flow_z2"].transform(
        lambda s: s.rolling(WINDOW, min_periods=WINDOW).mean()
    )
    denom = d["flow_main"].clip(lower=0.05)
    d["z1_share"] = d["flow_z1"] / denom
    d["z2_share"] = d["flow_z2"] / denom
    d["flow_delta"] = grp.diff().fillna(0)
    d["continuous_flow_sec"] = grp.transform(_continuous_flow)

    return d.dropna(subset=FEATURES).drop(columns=["_run"]).reset_index(drop=True)
