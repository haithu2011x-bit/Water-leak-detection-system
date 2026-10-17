import argparse
import json
import sqlite3
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score

from features import FEATURES, make_features

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "water.db"
MODEL_PATH = ROOT / "ai" / "iforest.joblib"
META_PATH = ROOT / "ai" / "iforest_meta.json"


def load_model():
    if not MODEL_PATH.exists() or not META_PATH.exists():
        raise SystemExit("Chua co model: hay chay python ai/train_iforest.py truoc")
    return joblib.load(MODEL_PATH), json.loads(META_PATH.read_text(encoding="utf-8"))


def read_db(limit=None, max_id=None):
    if not DB.exists():
        raise SystemExit(f"Khong thay database: {DB}")
    query = """SELECT id, ts_server, flow_main, flow_z1, flow_z2,
                      COALESCE(label,'') AS label,
                      COALESCE(scenario_id,'') AS scenario_id
               FROM telemetry """
    params = []
    if max_id is not None:
        query += " WHERE id <= ? "
        params.append(int(max_id))
    query += " ORDER BY id DESC "
    if limit is not None:
        query += " LIMIT ? "
        params.append(int(limit))
    with sqlite3.connect(DB) as con:
        return pd.read_sql_query(query, con, params=params).sort_values("id").reset_index(drop=True)


def identify_zone(row, meta):
    """Heuristic dua tren 3 flow + baseline, KHONG phai dinh vi chac chan."""
    b = meta["baseline"]
    res = float(row["balance_residual"])
    t_res = max(0.20, 4 * b["residual"]["std"])
    if res - b["residual"]["median"] > t_res:
        return "main/unmetered", f"Mat can bang luu luong +{res:.2f} L/min"

    dz1 = float(row["z1_mean_10"]) - b["z1"]["median"]
    dz2 = float(row["z2_mean_10"]) - b["z2"]["median"]
    t_z1 = max(0.20, 4 * b["z1"]["std"])
    t_z2 = max(0.20, 4 * b["z2"]["std"])
    if dz1 > t_z1 and dz2 <= t_z2:
        return "Zone 1 (nghi ngo)", f"Flow Zone 1 +{dz1:.2f} L/min so voi baseline"
    if dz2 > t_z2 and dz1 <= t_z1:
        return "Zone 2 (nghi ngo)", f"Flow Zone 2 +{dz2:.2f} L/min so voi baseline"
    return "khong chac zone", "Dau hieu luu luong khong du de dinh vi"


def predict_rows(model, meta, features):
    if features.empty:
        raise ValueError("Khong du 10 mau flow lien tiep de tinh feature")
    if meta["features"] != FEATURES:
        raise ValueError("Danh sach feature thay doi: hay train lai model")
    result = features.copy()
    result["anomaly_score"] = -model.score_samples(result[FEATURES])
    result["is_anomaly"] = result["anomaly_score"] > float(meta["threshold"])
    return result


def evaluate(model, meta):
    df = read_db(max_id=meta["data_max_id"])
    normal_test_ids = set(meta["normal_test_ids"])
    normal_test = df[df["id"].isin(normal_test_ids)].copy()
    leak_test = df[df["label"].str.lower().eq("leak")].copy()
    # Tao feature tren tung tap test rieng. Khong dung tap train hay label lam feature.
    normal_features = make_features(normal_test)
    leak_features = make_features(leak_test)
    if normal_features.empty or leak_features.empty:
        raise SystemExit("Khong du mau test; can >= 10 mau lien tiep cho moi kich ban")
    test = pd.concat([normal_features, leak_features], ignore_index=True).sort_values("id")
    predicted = predict_rows(model, meta, test)
    y_true = predicted["label"].str.lower().eq("leak").astype(int)
    y_pred = predicted["is_anomaly"].astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if fp + tn else 0.0
    print("DANH GIA THU (simulation, KHONG phai ket qua cam bien that)")
    print(f"Normal test={len(normal_features)}; Leak test={len(leak_features)}")
    print(f"TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"Precision={precision_score(y_true,y_pred,zero_division=0):.3f}")
    print(f"Recall={recall_score(y_true,y_pred,zero_division=0):.3f}")
    print(f"F1={f1_score(y_true,y_pred,zero_division=0):.3f}")
    print(f"False alarm rate={fpr:.3f}")
    print("Theo kich ban (ty le phat hien trong mau leak):")
    for scenario, group in predicted[predicted["label"].eq("leak")].groupby("scenario_id"):
        if not scenario:
            scenario = "khong co ma"
        rate = 100 * group["is_anomaly"].mean()
        print(f"  {scenario}: {int(group['is_anomaly'].sum())}/{len(group)} ({rate:.1f}%)")
    print("Luu y: normal goc rat don dieu; can thu tap nhieu trang thai normal doc lap de danh gia dung.")


def latest(model, meta, return_id=False):
    raw = read_db(limit=240)
    if raw.empty:
        print("Database chua co du lieu")
        return None
    out = make_features(raw)
    if out.empty or int(out.iloc[-1]["id"]) != int(raw.iloc[-1]["id"]):
        print("Chua du 10 mau lien tiep hop le trong lan gui gan nhat")
        return None
    row = predict_rows(model, meta, out.tail(1)).iloc[-1]
    score = float(row["anomaly_score"])
    status = "BAT THUONG (nghi ro ri)" if row["is_anomaly"] else "BINH THUONG theo model"
    print(f"id={int(row['id'])} | {row['ts_server']} | {status}")
    print(f"  Score={score:.5f} | Nguong={meta['threshold']:.5f}")
    print(f"  Main={row['flow_main']:.2f} | Z1={row['flow_z1']:.2f} | Z2={row['flow_z2']:.2f} L/min")
    if row["is_anomaly"]:
        zone, explanation = identify_zone(row, meta)
        print(f"  Zone: {zone} | Ly do: {explanation}")
    return int(row["id"]) if return_id else None


def watch(model, meta, interval=2.0):
    print("Theo doi du lieu moi; Ctrl+C de dung")
    previous_id = None
    try:
        while True:
            with sqlite3.connect(DB) as con:
                current_id = con.execute("SELECT max(id) FROM telemetry").fetchone()[0]
            if current_id is not None and current_id != previous_id:
                latest(model, meta)
                previous_id = current_id
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nDa dung theo doi")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["evaluate", "latest", "watch"], default="evaluate")
    args = parser.parse_args()
    model, meta = load_model()
    if args.mode == "evaluate":
        evaluate(model, meta)
    elif args.mode == "latest":
        latest(model, meta)
    else:
        watch(model, meta)


if __name__ == "__main__":
    main()
