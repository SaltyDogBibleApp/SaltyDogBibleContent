#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

VALID_CATEGORIES = {
    "Legislation / NDAA","Policy","Pay & Benefits","Retirement",
    "VA / Veteran Benefits","Training & Readiness","Admin","Other",
}
OFFICIAL_HOST_SUFFIXES = {
    "mynavyhr.navy.mil","navyreserve.navy.mil","govinfo.gov",
    "dfas.mil","va.gov","bls.gov","defense.gov",
}
STATUS_BY_SOURCE_TYPE = {
    "navadmin":"TRACKING","reserve_guidance":"TRACKING","legislation":"INTRODUCED",
    "pay_tables":"TRACKING","va_benefits":"TRACKING",
    "economic_release":"TRACKING","dod_compensation":"TRACKING",
}
HIGH_PRIORITY_SIGNALS = {
    "RESERVE","SELRES","RETIREMENT","DRILL PAY","ANNUAL TRAINING",
    "CONTINUATION","CYBERSECURITY","CBRN","DUTY STATUS","NDAA",
}

def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def slugify(value):
    value = re.sub(r"[^a-z0-9]+","-",value.lower().strip())
    return re.sub(r"-+","-",value).strip("-")[:90] or "reserve-intel-draft"

def short_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()[:10]

def host_is_official(url):
    host = (urlparse(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in OFFICIAL_HOST_SUFFIXES)

def parse_csvish(value):
    value = value.strip()
    if not value or value.lower() in {"review required","curated source change"}:
        return []
    return [p.strip() for p in value.split(",") if p.strip()]

def parse_monitor_report(text):
    if "## New potentially relevant items" not in text:
        return []
    section = text.split("## New potentially relevant items",1)[1]
    if "\n## " in section:
        section = section.split("\n## ",1)[0]
    if "None detected." in section:
        return []
    blocks = re.split(r"\n###\s+", section)
    results = []
    for raw in blocks[1:]:
        lines = [x.rstrip() for x in raw.strip().splitlines()]
        if not lines:
            continue
        title = lines[0].strip()
        fields = {}
        for line in lines[1:]:
            m = re.match(r"^-\s+([^:]+):\s+(.*)$", line.strip())
            if not m:
                continue
            fields[m.group(1).strip().lower()] = m.group(2).strip().replace("**","").replace("`","")
        source_name = fields.get("source","").strip()
        source_type = fields.get("type","").strip()
        source_url = fields.get("url","").strip()
        if not title or not source_name or not source_url:
            continue
        results.append({
            "title": title,
            "sourceName": source_name,
            "sourceType": source_type,
            "sourceURL": source_url,
            "signals": parse_csvish(fields.get("reserve signals","")),
            "categoryHints": parse_csvish(fields.get("category hints","")),
            "listedDate": fields.get("listed date") or None,
        })
    return results

def choose_category(candidate):
    for c in candidate.get("categoryHints",[]):
        if c in VALID_CATEGORIES:
            return c
    return "Other"

def choose_priority(candidate):
    signals = {s.upper() for s in candidate.get("signals",[])}
    return "HIGH" if signals & HIGH_PRIORITY_SIGNALS else "NORMAL"

def audience(candidate):
    st = candidate.get("sourceType","")
    sn = candidate.get("sourceName","").lower()
    service = "USN" if st in {"navadmin","reserve_guidance"} or "navy" in sn else "ALL"
    return {"service":service,"reserveStatus":"ALL","trainingWing":None,"squadron":None}

def make_draft(candidate, detected_at):
    article_id = f"intel-{slugify(candidate['title'])[:64]}-{short_hash(candidate['sourceURL'])}"
    signals = ", ".join(candidate.get("signals",[]))
    signal_phrase = f" Detected Reserve signals: {signals}." if signals else ""
    return {
        "draftSchemaVersion":1,
        "draftStatus":"PENDING_HUMAN_REVIEW",
        "requiresHumanReview":True,
        "publishReady":False,
        "detectedAt":detected_at,
        "sourceEvidence":{
            "sourceName":candidate["sourceName"],
            "sourceType":candidate["sourceType"],
            "sourceURL":candidate["sourceURL"],
            "listedDate":candidate.get("listedDate"),
            "reserveSignals":candidate.get("signals",[]),
            "categoryHints":candidate.get("categoryHints",[]),
            "officialHostVerified":host_is_official(candidate["sourceURL"]),
        },
        "reviewChecklist":{
            "sourceOpenedAndRead":False,
            "factsVerifiedAgainstSource":False,
            "statusVerified":False,
            "effectiveDateVerified":False,
            "audienceVerified":False,
            "summaryRewrittenFromSource":False,
            "whyItMattersRewrittenFromSource":False,
            "detailsRewrittenFromSource":False,
            "approvedForPublication":False,
        },
        "articleDraft":{
            "id":article_id,
            "publishedAt":detected_at,
            "updatedAt":detected_at,
            "title":candidate["title"],
            "category":choose_category(candidate),
            "status":STATUS_BY_SOURCE_TYPE.get(candidate.get("sourceType"),"TRACKING"),
            "priority":choose_priority(candidate),
            "summary":f"Automated draft from an official source: {candidate['title']}. Review the source before publishing any policy conclusion.",
            "whyItMatters":"This official-source item may affect Reserve policy, readiness, pay, benefits, retirement, or administration. Human review is required to determine the actual Reserve impact before publication." + signal_phrase,
            "details":"This draft was created automatically from Reserve Intel source monitoring. Open and review the authoritative source before publication. Confirm what changed, who is affected, whether the item is proposed or effective, the applicable dates, and any implementation guidance. Replace this placeholder with a sourced explanation before approving the article.",
            "effectiveDate":None,
            "sourceName":candidate["sourceName"],
            "sourceURL":candidate["sourceURL"],
            "audience":audience(candidate),
            "isPinned":False,
            "isActive":False,
        }
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", default="automation/monitor-report.md")
    p.add_argument("--output-dir", default="drafts/pending")
    p.add_argument("--detected-at", default=None)
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()

    if a.self_test:
        sample = """# Reserve Intel Monitor Report

## New potentially relevant items

### NAVADMIN 999/26 — RESERVE CYBERSECURITY TEST

- Source: **MyNavyHR NAVADMIN**
- Type: `navadmin`
- URL: https://www.mynavyhr.navy.mil/test.pdf
- Reserve signals: RESERVE, CYBERSECURITY
- Category hints: Training & Readiness, Admin
- Listed date: 9/15/2026

## Publishing safety
"""
        c = parse_monitor_report(sample)
        assert len(c) == 1
        d = make_draft(c[0], "2026-09-15T14:00:00Z")
        assert d["publishReady"] is False
        assert d["articleDraft"]["category"] == "Training & Readiness"
        assert d["articleDraft"]["priority"] == "HIGH"
        assert d["articleDraft"]["isActive"] is False
        print("SELF-TEST PASSED")
        return 0

    report = Path(a.report)
    if not report.exists():
        print(f"Monitor report not found: {report}", file=sys.stderr)
        return 2

    candidates = parse_monitor_report(report.read_text(encoding="utf-8"))
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    detected_at = a.detected_at or utc_now_iso()
    created = 0
    existing = 0
    for c in candidates:
        draft = make_draft(c, detected_at)
        path = out / f"{draft['articleDraft']['id']}.json"
        if path.exists():
            existing += 1
            continue
        path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        created += 1
        print("CREATED", path)

    print(f"Draft generation complete: candidates={len(candidates)}, created={created}, existing={existing}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
