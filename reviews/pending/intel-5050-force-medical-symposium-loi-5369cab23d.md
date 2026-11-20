# Reserve Intel Review

> **Human approval required.** Nothing in this review is live in the app yet.
> Merging this pull request is the approval action. The publish workflow will
> refuse to publish unless every approval checkbox below is checked.

### Review Mode

- Source-specific automation: **Navy Reserve guidance fingerprint verification applied**
- Automated policy-change attribution: **Not claimed**
- Effective-date inference from HTTP metadata: **Not performed**
- Human source verification and rewrite: **Required before approval**

## 5050 - FORCE MEDICAL SYMPOSIUM LOI

| Field | Proposed value |
| --- | --- |
| Category | Policy |
| Status | TRACKING |
| Priority | NORMAL |
| Service | USN |
| Reserve status | ALL |
| Training Wing | All |
| Squadron | All |

### Summary

The Reserve Intel monitor detected a newly linked official Navy Reserve guidance document: 5050 - FORCE MEDICAL SYMPOSIUM LOI. The current PDF was re-fetched and matches the fingerprint captured at detection. Human review is required before describing its policy effect.

### Why It Matters

Official Navy Reserve personnel guidance can affect Reserve administration, training, readiness, pay or benefits, retirement, assignments, and related member requirements. The automated detection does not establish which of those areas changed or who is affected. Review the source before making any Salty Dog Bible content or app change.

### Details

Automated evidence verification for 5050 - FORCE MEDICAL SYMPOSIUM LOI: detection kind `new_linked_document`. The official Navy Reserve PDF was re-fetched from https://www.navyreserve.navy.mil/Portals/35/5050%20-%20FORCE%20MEDICAL%20SYMPOSIUM%20LOI.pdf and its SHA-256 fingerprint matched the fingerprint stored with the detected draft. Source-server metadata observed during verification: HTTP Last-Modified: Fri, 20 Nov 2026 19:01:40 GMT; downloaded size: 176,858 bytes. HTTP Last-Modified metadata is not treated as a policy effective date or revision date. The monitor detected a new linked official Navy Reserve guidance PDF. Automated tooling verified the current document fingerprint but has not determined the document's policy effect. Human source review is required.

### Official Source

**Navy Reserve RESFOR Notices**

https://www.navyreserve.navy.mil/Portals/35/5050 - FORCE MEDICAL SYMPOSIUM LOI.pdf

### Detection Evidence

- Source type: `reserve_guidance`
- Listed date: Not supplied
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Official host verified: Yes
- Detection kind: `new_linked_document`
- Source fingerprint: `7554303b0d901bd72a1036300986109e9bd54789d07fa71bf720e973dd6281cc`

### Navy Reserve Guidance Enrichment Evidence

- Enriched at: 2026-11-20T20:08:00Z
- Document kind: Navy Reserve guidance
- Document identifier: Not supplied
- Source filename: 5050 - FORCE MEDICAL SYMPOSIUM LOI.pdf
- Fetched URL: https://www.navyreserve.navy.mil/Portals/35/5050%20-%20FORCE%20MEDICAL%20SYMPOSIUM%20LOI.pdf
- Detected fingerprint: `7554303b0d901bd72a1036300986109e9bd54789d07fa71bf720e973dd6281cc`
- Observed fingerprint: `7554303b0d901bd72a1036300986109e9bd54789d07fa71bf720e973dd6281cc`
- Fingerprint matched detected version: Yes
- HTTP Last-Modified: Fri, 20 Nov 2026 19:01:40 GMT
- Downloaded size: 176,858 bytes
- ETag: Not supplied
- Automated change attribution claimed: No
- Effective date inferred from HTTP metadata: No
- Change-attribution note: The monitor detected a new linked official Navy Reserve guidance PDF. Automated tooling verified the current document fingerprint but has not determined the document's policy effect. Human source review is required.

> HTTP Last-Modified is source-server metadata only. It is **not** treated
> as the document's policy effective date or authoritative revision date.

### Current PDF Text Extraction

- Snapshot available: Yes
- Extraction status: ok
- Extraction method: pypdf
- Extracted text SHA-256: `59bea51e08858e9d0e557267aad628530a713e563c8a070dcdfdb689b43e4fa9`
- PDF pages: 3
- Pages with extracted text: 3
- Extracted characters: 5051
- Extracted lines: 86
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
- Potentially affected features: Readiness Tracker, Admin Gouge
- Tagging basis: category: Policy, keyword: READINESS
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

<!-- reserve-intel-article-id: intel-5050-force-medical-symposium-loi-5369cab23d -->
