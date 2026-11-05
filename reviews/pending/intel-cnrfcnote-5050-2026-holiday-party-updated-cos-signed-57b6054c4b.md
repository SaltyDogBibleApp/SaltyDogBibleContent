# Reserve Intel Review

> **Human approval required.** Nothing in this review is live in the app yet.
> Merging this pull request is the approval action. The publish workflow will
> refuse to publish unless every approval checkbox below is checked.

### Review Mode

- Source-specific automation: **Navy Reserve guidance fingerprint verification applied**
- Automated policy-change attribution: **Not claimed**
- Effective-date inference from HTTP metadata: **Not performed**
- Human source verification and rewrite: **Required before approval**

## CNRFCNOTE 5050 - 2026 HOLIDAY PARTY updated (COS signed)

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

The Reserve Intel monitor detected a newly linked official Navy Reserve guidance document: CNRFCNOTE 5050 - 2026 HOLIDAY PARTY updated (COS signed). The current PDF was re-fetched and matches the fingerprint captured at detection. Human review is required before describing its policy effect.

### Why It Matters

Official Navy Reserve personnel guidance can affect Reserve administration, training, readiness, pay or benefits, retirement, assignments, and related member requirements. The automated detection does not establish which of those areas changed or who is affected. Review the source before making any Salty Dog Bible content or app change.

### Details

Automated evidence verification for CNRFCNOTE 5050 - 2026 HOLIDAY PARTY updated (COS signed): detection kind `new_linked_document`. The official Navy Reserve PDF was re-fetched from https://www.navyreserve.navy.mil/Portals/35/CNRFCNOTE%205050%20-%202026%20HOLIDAY%20PARTY%20updated%20(COS%20signed).pdf and its SHA-256 fingerprint matched the fingerprint stored with the detected draft. Source-server metadata observed during verification: HTTP Last-Modified: Wed, 04 Nov 2026 18:09:47 GMT; downloaded size: 165,376 bytes. HTTP Last-Modified metadata is not treated as a policy effective date or revision date. The monitor detected a new linked official Navy Reserve guidance PDF. Automated tooling verified the current document fingerprint but has not determined the document's policy effect. Human source review is required.

### Official Source

**Navy Reserve RESFOR Notices**

https://www.navyreserve.navy.mil/Portals/35/CNRFCNOTE 5050 - 2026 HOLIDAY PARTY updated (COS signed).pdf

### Detection Evidence

- Source type: `reserve_guidance`
- Listed date: Not supplied
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Official host verified: Yes
- Detection kind: `new_linked_document`
- Source fingerprint: `4bfffbf4041366cf937051db7a6e2a87c3375863b9d49cd08c86d4294a0d4468`

### Navy Reserve Guidance Enrichment Evidence

- Enriched at: 2026-11-05T19:54:40Z
- Document kind: Navy Reserve guidance
- Document identifier: Not supplied
- Source filename: CNRFCNOTE 5050 - 2026 HOLIDAY PARTY updated (COS signed).pdf
- Fetched URL: https://www.navyreserve.navy.mil/Portals/35/CNRFCNOTE%205050%20-%202026%20HOLIDAY%20PARTY%20updated%20(COS%20signed).pdf
- Detected fingerprint: `4bfffbf4041366cf937051db7a6e2a87c3375863b9d49cd08c86d4294a0d4468`
- Observed fingerprint: `4bfffbf4041366cf937051db7a6e2a87c3375863b9d49cd08c86d4294a0d4468`
- Fingerprint matched detected version: Yes
- HTTP Last-Modified: Wed, 04 Nov 2026 18:09:47 GMT
- Downloaded size: 165,376 bytes
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
- Extracted text SHA-256: `9ad57ed36a5bb8cffa85d51769cb28efcd0d2ae7440da54f1980d1137eed4de2`
- PDF pages: 2
- Pages with extracted text: 2
- Extracted characters: 1973
- Extracted lines: 50
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

<!-- reserve-intel-article-id: intel-cnrfcnote-5050-2026-holiday-party-updated-cos-signed-57b6054c4b -->
