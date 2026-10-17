"""Independent HOLDOUT evaluation on real experiment-session CSV only.

Never overwrites model/meta or self-approves a candidate. Distinct experiment
sessions are mandatory, and none may occur in model's training/validation list.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from datetime import datetime,timezone
from pathlib import Path

import joblib
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from ai.features import FEATURES
from ai.train_real import load_verified_session


def evaluate(model,meta,files):
    if meta.get("features")!=FEATURES:
        raise ValueError("Model feature schema does not match")
    threshold=meta.get("threshold")
    if type(threshold) not in (float,int) or not math.isfinite(threshold):
        raise ValueError("Invalid anomaly threshold")
    previously_seen=set(str(x) for x in meta.get("experiment_ids",[]))
    reviewed=set()
    detailed=[]
    total={"tp":0,"tn":0,"fp":0,"fn":0}
    for file in files:
        raw,features,sid=load_verified_session(file,normal_only=False)
        if sid in previously_seen or sid in reviewed:
            raise ValueError("Holdout session reused in training/validation or twice in tests: "+sid)
        reviewed.add(sid)
        label=str(raw["label"].iloc[0])
        score=-np.asarray(model.score_samples(features[FEATURES]),dtype=float)
        if not np.isfinite(score).all():
            raise ValueError("Model produced non-finite score for "+str(file))
        predicted=score>threshold
        if label=="leak":
            tp=int(predicted.sum())
            fn=int((~predicted).sum())
            total["tp"]+=tp
            total["fn"]+=fn
        else:
            fp=int(predicted.sum())
            tn=int((~predicted).sum())
            total["fp"]+=fp
            total["tn"]+=tn
        detailed.append({"experiment_id":sid,"scenario_id":str(raw["scenario_id"].iloc[0]),
            "actual":label,"samples":len(predicted),
            "anomaly_count":int(predicted.sum())})
    if not any(d["actual"]=="normal" for d in detailed) or not any(d["actual"]=="leak" for d in detailed):
        raise ValueError("Independent holdout must contain both REAL normal and REAL leak sessions")
    tp,tn,fp,fn=(total[k] for k in ("tp","tn","fp","fn"))
    precision=tp/(tp+fp) if tp+fp else 0
    recall=tp/(tp+fn) if tp+fn else 0
    f1=(2*precision*recall/(precision+recall)) if precision+recall else 0
    fpr=fp/(fp+tn) if fp+tn else 0
    return {"evaluated_utc":datetime.now(timezone.utc).isoformat(),
            "holdout_session_ids":sorted(reviewed), "confusion":total,
            "precision":round(precision,6),"recall":round(recall,6),
            "f1":round(f1,6),"false_positive_rate":round(fpr,6),
            "per_session":detailed,
            "approval_note":"Diagnostic only. Human review of real experiments still required."}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--model",type=Path,default=ROOT/"ai"/"iforest_real_candidate.joblib")
    parser.add_argument("--meta",type=Path,default=ROOT/"ai"/"iforest_real_candidate_meta.json")
    parser.add_argument("--holdout",type=Path,nargs="+",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error("Report exists; refusing to overwrite")
    meta=json.loads(args.meta.read_text(encoding="utf-8"))
    model=joblib.load(args.model)  # only from trusted local files
    report=evaluate(model,meta,args.holdout)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Holdout report:",args.output)
    print("F1:",report["f1"],"False alarm rate:",report["false_positive_rate"])
    print("NOT AUTO-APPROVED: inspect errors, leak-zone limitations and hardware evidence.")


if __name__=="__main__":
    main()
