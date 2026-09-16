# Reserve Intel Review

> **Human approval required.** Nothing in this review is live in the app yet.
> Merging this pull request is the approval action. The publish workflow will
> refuse to publish unless every approval checkbox below is checked.

### Review Mode

- Source-specific automation: **Navy Reserve guidance fingerprint verification applied**
- Automated policy-change attribution: **Not claimed**
- Effective-date inference from HTTP metadata: **Not performed**
- Human source verification and rewrite: **Required before approval**

## COMNAVRESFORNOTE 1570 IDT-R

| Field | Proposed value |
| --- | --- |
| Category | Policy |
| Status | TRACKING |
| Priority | HIGH |
| Service | USN |
| Reserve status | ALL |
| Training Wing | All |
| Squadron | All |

### Summary

The Reserve Intel monitor detected a newly linked official Navy Reserve guidance document: COMNAVRESFORNOTE 1570 IDT-R. The current PDF was re-fetched and matches the fingerprint captured at detection. Human review is required before describing its policy effect.

### Why It Matters

Official Navy Reserve personnel guidance can affect Reserve administration, training, readiness, pay or benefits, retirement, assignments, and related member requirements. The automated detection does not establish which of those areas changed or who is affected. Review the source before making any Salty Dog Bible content or app change.

### Details

Automated evidence verification for COMNAVRESFORNOTE 1570 IDT-R: detection kind `new_linked_document`. The official Navy Reserve PDF was re-fetched from https://www.navyreserve.navy.mil/Portals/35/COMNAVRESFORNOTE%201570%20IDT-R.pdf and its SHA-256 fingerprint matched the fingerprint stored with the detected draft. Source-server metadata observed during verification: HTTP Last-Modified: Thu, 29 Jan 2026 16:15:28 GMT; downloaded size: 562,628 bytes. HTTP Last-Modified metadata is not treated as a policy effective date or revision date. The monitor detected a new linked official Navy Reserve guidance PDF. Automated tooling verified the current document fingerprint but has not determined the document's policy effect. Human source review is required.

### Official Source

**Navy Reserve RESFOR Notices**

https://www.navyreserve.navy.mil/Portals/35/COMNAVRESFORNOTE 1570 IDT-R.pdf

### Detection Evidence

- Source type: `reserve_guidance`
- Listed date: Not supplied
- Reserve signals: INACTIVE DUTY TRAINING, IDT-R, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, SELRES, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE
- Official host verified: Yes
- Detection kind: `new_linked_document`
- Source fingerprint: `48105009764fee4944110b986f17988f7187a04b2fd6dc8ae46bb9fbaeb44f8e`

### Navy Reserve Guidance Enrichment Evidence

- Enriched at: 2026-09-16T20:36:21Z
- Document kind: COMNAVRESFORNOTE
- Document identifier: Not supplied
- Source filename: COMNAVRESFORNOTE 1570 IDT-R.pdf
- Fetched URL: https://www.navyreserve.navy.mil/Portals/35/COMNAVRESFORNOTE%201570%20IDT-R.pdf
- Detected fingerprint: `48105009764fee4944110b986f17988f7187a04b2fd6dc8ae46bb9fbaeb44f8e`
- Observed fingerprint: `48105009764fee4944110b986f17988f7187a04b2fd6dc8ae46bb9fbaeb44f8e`
- Fingerprint matched detected version: Yes
- HTTP Last-Modified: Thu, 29 Jan 2026 16:15:28 GMT
- Downloaded size: 562,628 bytes
- ETag: Not supplied
- Automated change attribution claimed: No
- Effective date inferred from HTTP metadata: No
- Change-attribution note: The monitor detected a new linked official Navy Reserve guidance PDF. Automated tooling verified the current document fingerprint but has not determined the document's policy effect. Human source review is required.

> HTTP Last-Modified is source-server metadata only. It is **not** treated
> as the document's policy effective date or authoritative revision date.

### Current PDF Text Extraction

- Snapshot available: Yes
- Extraction status: no_extractable_text
- Extraction method: pypdf
- Extracted text SHA-256: `Not supplied`
- PDF pages: 12
- Pages with extracted text: 0
- Extracted characters: 0
- Extracted lines: 0
- Extraction truncated by safety limit: No

### Extracted Text Comparison

- Comparison available: No
- Policy interpretation claimed: No
- Reason unavailable: new_linked_document_has_no_prior_version

> This is a newly linked document, so there is no earlier monitored version to compare. Human source review is required.

### Potential Salty Dog Bible Impact

> **Informational only.** These tags are an automated first-pass for the reviewer.
> They do not change app behavior, app content, or the live Reserve Intel feed.

- App review recommended: Yes
- Potentially affected features: Drill / Orders, Readiness Tracker, Admin Gouge
- Tagging basis: category: Policy, keyword: IDT, keyword: READINESS
- Note: Automated first-pass only. Human review is required before making any Salty Dog Bible app or content change.

## Approval Checklist

- [ ] I opened the official source.
- [ ] I verified the facts against the official source.
- [ ] I verified the status and effective date.
- [ ] I verified the intended audience.
- [ ] I reviewed the title, summary, Why It Matters, and details.
- [ ] I approve publication to Reserve Intel.

### What the buttons mean

- **Merge pull request** = approve this article for publication.
- **Close pull request** = reject / do not publish.

The live `reserve-content-feed.json` is not changed by this review PR itself.
Publication happens only after a merged PR passes the approval gate.

<!-- reserve-intel-article-id: intel-comnavresfornote-1570-idt-r-18807ddb1d -->
