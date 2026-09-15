#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from urllib.parse import urlparse

VALID_CATEGORIES={"Legislation / NDAA","Policy","Pay & Benefits","Retirement","VA / Veteran Benefits","Training & Readiness","Admin","Other"}
VALID_STATUSES={"TRACKING","PROPOSED","INTRODUCED","COMMITTEE","PASSED HOUSE","PASSED SENATE","SIGNED","EFFECTIVE","SUPERSEDED"}
VALID_PRIORITIES={"NORMAL","HIGH"}
VALID_SERVICES={"ALL","USN","USMC"}
VALID_RESERVE_STATUSES={"ALL","SELRES","VTU"}
CHECKLIST={"sourceOpenedAndRead","factsVerifiedAgainstSource","statusVerified","effectiveDateVerified","audienceVerified","summaryRewrittenFromSource","whyItMattersRewrittenFromSource","detailsRewrittenFromSource","approvedForPublication"}

def fail(msg): raise ValueError(msg)
def nonempty(v,label):
    if not isinstance(v,str) or not v.strip(): fail(f"{label} must be a non-empty string.")
    return v.strip()
def https(v,label):
    p=urlparse(v)
    if p.scheme!="https" or not p.hostname: fail(f"{label} must be a valid https URL.")

def validate(payload,name):
    if payload.get("draftSchemaVersion") != 1: fail(f"{name}: draftSchemaVersion must be 1.")
    if payload.get("draftStatus") != "PENDING_HUMAN_REVIEW": fail(f"{name}: wrong draftStatus.")
    if payload.get("requiresHumanReview") is not True: fail(f"{name}: requiresHumanReview must be true.")
    if payload.get("publishReady") is not False: fail(f"{name}: publishReady must be false.")

    ev=payload.get("sourceEvidence")
    if not isinstance(ev,dict): fail(f"{name}: sourceEvidence missing.")
    https(nonempty(ev.get("sourceURL"),f"{name}.sourceEvidence.sourceURL"),f"{name}.sourceEvidence.sourceURL")

    cl=payload.get("reviewChecklist")
    if not isinstance(cl,dict): fail(f"{name}: reviewChecklist missing.")
    missing=CHECKLIST-set(cl)
    if missing: fail(f"{name}: reviewChecklist missing {sorted(missing)}")
    if any(not isinstance(cl[k],bool) for k in CHECKLIST): fail(f"{name}: checklist values must be boolean.")

    a=payload.get("articleDraft")
    if not isinstance(a,dict): fail(f"{name}: articleDraft missing.")
    for k in ("id","title","summary","whyItMatters","details","sourceName","sourceURL"):
        nonempty(a.get(k),f"{name}.articleDraft.{k}")
    https(a["sourceURL"],f"{name}.articleDraft.sourceURL")
    if a.get("category") not in VALID_CATEGORIES: fail(f"{name}: bad category.")
    if a.get("status") not in VALID_STATUSES: fail(f"{name}: bad status.")
    if a.get("priority") not in VALID_PRIORITIES: fail(f"{name}: bad priority.")
    aud=a.get("audience")
    if not isinstance(aud,dict): fail(f"{name}: audience missing.")
    if aud.get("service") not in VALID_SERVICES: fail(f"{name}: bad audience.service.")
    if aud.get("reserveStatus") not in VALID_RESERVE_STATUSES: fail(f"{name}: bad audience.reserveStatus.")
    if a.get("isActive") is not False: fail(f"{name}: pending draft must have isActive=false.")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("path",nargs="?",default="drafts/pending")
    a=p.parse_args()
    target=Path(a.path)
    files=sorted(target.glob("*.json")) if target.is_dir() else ([target] if target.is_file() else [])
    if not files:
        print("VALID: no pending draft JSON files found.")
        return 0
    try:
        for f in files:
            payload=json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(payload,dict): fail(f"{f.name}: root must be object.")
            validate(payload,f.name)
    except (OSError,json.JSONDecodeError,ValueError) as exc:
        print(f"INVALID: {exc}",file=sys.stderr)
        return 1
    print(f"VALID: {len(files)} pending draft(s).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
