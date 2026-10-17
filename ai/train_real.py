"""Prepare Isolation Forest training from OPERATOR-CONFIRMED real session CSV only.

This script is NOT run before hardware is available. It does not use
water.db, fake_sensor, or simulation-trained models; it cannot approve itself.
Train and validation inputs must contain distinct experiment_id values.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
import joblib

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from ai.features import FEATURES, make_features

COLUMNS={"id","ts_server","flow_main","flow_z1","flow_z2",
         "label","scenario_id","experiment_id","source"}
REAL_SOURCE="real_operator_confirmed"


def load_verified_session(path, normal_only=True):
    """Fail when source/label/flow is ambiguous; no fallback or guessed labels."""
    path=Path(path)
    df=pd.read_csv(path, dtype={"scenario_id":"string","source":"string","label":"string"})
    if not COLUMNS <= set(df.columns):
        raise ValueError(f"{path}: missing {sorted(COLUMNS-set(df.columns))}")
    if len(df)<30:
        raise ValueError(f"{path}: require >=30 consecutive real samples")
    if df["experiment_id"].isna().any() or df["experiment_id"].nunique()!=1:
        raise ValueError(f"{path}: expect one experiment_id per file")
    if not df["source"].eq(REAL_SOURCE).all():
        raise ValueError(f"{path}: input is not operator-confirmed real-session export")
    allowed={"normal"} if normal_only else {"normal","leak"}
    if not df["label"].isin(allowed).all() or df["label"].nunique()!=1:
        raise ValueError(f"{path}: unacceptable or mixed label")
    df["id"]=pd.to_numeric(df["id"],errors="coerce")
    if df["id"].isna().any() or not df["id"].diff().iloc[1:].eq(1).all():
        raise ValueError(f"{path}: non-contiguous IDs")
    ts=pd.to_datetime(df["ts_server"],errors="coerce",utc=True)
    if ts.isna().any() or not ts.diff().dt.total_seconds().iloc[1:].between(0.5,2.5).all():
        raise ValueError(f"{path}: missing or non-contiguous server timestamp")
    for name in ("flow_main","flow_z1","flow_z2"):
        df[name]=pd.to_numeric(df[name],errors="coerce")
        if not np.isfinite(df[name]).all() or (df[name]<0).any() or (df[name]>6).any():
            raise ValueError(f"{path}: out-of-range values for {name}")
        if ((df[name]>0)&(df[name]<0.3)).any():
            raise ValueError(f"{path}: values below YF-S401 nominal range for {name}")
    features=make_features(df)
    if len(features)<20:
        raise ValueError(f"{path}: not enough continuous feature rows")
    return df,features,str(df["experiment_id"].iloc[0])


def prepare_distinct_sessions(train_files, validation_files):
    """Disjoint experiment sessions; feature windows NEVER cross CSV boundaries."""
    train,valid,identities=[],[],set()
    raw=[]
    for group,files in ((train,train_files),(valid,validation_files)):
        for file in files:
            base,features,identity=load_verified_session(file)
            if identity in identities:
                raise ValueError(f"Repeated experiment_id across train/validation: {identity}")
            identities.add(identity)
            group.append(features)
            if group is train:
                raw.append(base)
    if not train or not valid:
        raise ValueError("Provide separate train and validation session CSVs")
    return pd.concat(train,ignore_index=True),pd.concat(valid,ignore_index=True),pd.concat(raw,ignore_index=True),identities


def train(train_files, validation_files, model_output, meta_output):
    training,validation,normal_raw,sessions=prepare_distinct_sessions(train_files,validation_files)
    if len(training)<100 or len(validation)<50:
        raise ValueError("Require >=100 train feature rows and >=50 independent validation rows")
    model_path,meta_path=Path(model_output),Path(meta_output)
    if model_path.exists() or meta_path.exists():
        raise FileExistsError("Refusing to overwrite existing model or metadata")
    model=IsolationForest(n_estimators=200,contamination="auto",random_state=42,n_jobs=-1)
    model.fit(training[FEATURES])
    threshold=float(np.quantile(-model.score_samples(validation[FEATURES]),0.99))
    def stats(values):
        return {"median":float(values.median()),"std":float(values.std(ddof=0))}
    raw_res=normal_raw["flow_main"]-normal_raw["flow_z1"]-normal_raw["flow_z2"]
    metadata={
        "version":"real-candidate-v1",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "features":FEATURES,"threshold":threshold,
        "threshold_method":"99th percentile of independent real normal validation sessions",
        "baseline":{"z1":stats(normal_raw["flow_z1"]),
                    "z2":stats(normal_raw["flow_z2"]),
                    "residual":stats(raw_res)},
        "provenance":"real_operator_confirmed",
        "approval_status":"NOT_APPROVED; independent held-out real leak/normal evaluation required",
        "train_feature_rows":len(training),"validation_feature_rows":len(validation),
        "experiment_ids":sorted(sessions),
    }
    model_path.parent.mkdir(parents=True,exist_ok=True)
    meta_path.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump(model,model_path)
    meta_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    return metadata


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--train",nargs="+",type=Path,required=True,help="One or more REAL normal-session CSVs")
    p.add_argument("--validation",nargs="+",type=Path,required=True,help="Independent REAL normal-session CSVs")
    p.add_argument("--model-out",type=Path,default=ROOT/"ai"/"iforest_real_candidate.joblib")
    p.add_argument("--meta-out",type=Path,default=ROOT/"ai"/"iforest_real_candidate_meta.json")
    args=p.parse_args()
    result=train(args.train,args.validation,args.model_out,args.meta_out)
    print("Real-only model CANDIDATE saved, NOT approved for live alerts.")
    print("Train features:",result["train_feature_rows"],"Validation features:",result["validation_feature_rows"])
    print("Independent real leak/normal holdout and operator approval STILL REQUIRED.")

if __name__=="__main__":
    main()
