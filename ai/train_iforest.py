
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from features import FEATURES, make_features

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "water.db"
MODEL_PATH = ROOT / "ai" / "iforest.joblib"
META_PATH = ROOT / "ai" / "iforest_meta.json"


def main():
    if not DB.exists():
        raise SystemExit(f"Khong thay database: {DB}")
    with sqlite3.connect(DB) as con:
        df = pd.read_sql_query("""
            SELECT id, ts_server, flow_main, flow_z1, flow_z2,
                   COALESCE(label, '') AS label,
                   COALESCE(scenario_id, '') AS scenario_id
            FROM telemetry ORDER BY id
        """, con)

    normal = df[df["label"].str.lower().eq("normal")].sort_values("id").reset_index(drop=True)
    unlabelled = df[df["label"].str.strip().eq("")]
    if len(normal) < 100:
        raise SystemExit(f"Chi co {len(normal)} mau normal; can it nhat 100 mau normal co nhan.")

    # Tach theo thoi gian, KHONG shuffle. Ba tap doc lap ve dong du lieu.
    n = len(normal)
    train_end = int(n * 0.60)
    valid_end = int(n * 0.80)
    train_raw = normal.iloc[:train_end].copy()
    valid_raw = normal.iloc[train_end:valid_end].copy()
    test_raw = normal.iloc[valid_end:].copy()

    train = make_features(train_raw)
    valid = make_features(valid_raw)
    test = make_features(test_raw)
    if min(len(train), len(valid), len(test)) < 20:
        raise SystemExit("Khong du mau lien tuc de train/validation/test. Nen thu lai normal >= 5 phut.")

    model = IsolationForest(n_estimators=200, contamination="auto", random_state=42, n_jobs=-1)
    model.fit(train[FEATURES])
    # Score lon => bat thuong; chon nguong tren VALIDATION normal doc lap.
    validation_scores = -model.score_samples(valid[FEATURES])
    threshold = float(np.quantile(validation_scores, 0.99))

    def stats(column):
        values = train_raw[column].astype(float)
        return {"median": float(values.median()), "std": float(values.std(ddof=0))}

    residual = train_raw["flow_main"] - train_raw["flow_z1"] - train_raw["flow_z2"]
    meta = {
        "version": "flow-only-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "features": FEATURES,
        "threshold": threshold,
        "threshold_method": "q99 of held-out normal validation anomaly scores",
        "sampling_note": "continuous_flow_sec assumes approximately 1 sample per second",
        "data_max_id": int(df["id"].max()),
        "normal_test_ids": [int(x) for x in test_raw["id"].tolist()],
        "counts": {
            "total": int(len(df)), "unlabelled_excluded": int(len(unlabelled)),
            "normal_train_raw": int(len(train_raw)),
            "normal_validation_raw": int(len(valid_raw)),
            "normal_test_raw": int(len(test_raw)),
            "normal_train_feature_rows": int(len(train)),
            "normal_validation_feature_rows": int(len(valid)),
            "normal_test_feature_rows": int(len(test)),
        },
        "baseline": {
            "z1": stats("flow_z1"), "z2": stats("flow_z2"),
            "residual": {"median": float(residual.median()),
                         "std": float(residual.std(ddof=0))},
        },
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("TRAIN HOAN THANH (CHi DU LIEU GIA LAP HIEN TAI)")
    print(f"Normal raw: train={len(train_raw)}, valid={len(valid_raw)}, test={len(test_raw)}")
    print(f"Feature rows: train={len(train)}, valid={len(valid)}, test={len(test)}")
    print(f"Bo qua {len(unlabelled)} mau chua co nhan")
    print(f"Nguong anomaly (q99 validation): {threshold:.5f}")
    print(f"Model: {MODEL_PATH}")
    print(f"Metadata: {META_PATH}")
    print("Tiep theo: python ai/detect.py --mode evaluate")


if __name__ == "__main__":
    main()
