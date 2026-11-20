# Reserve Intel Review

> **Human approval required.** Nothing in this review is live in the app yet.
> Merging this pull request is the approval action. The publish workflow will
> refuse to publish unless every approval checkbox below is checked.

### Review Mode

- Source-specific automation: **Navy Reserve guidance fingerprint verification applied**
- Automated policy-change attribution: **Not claimed**
- Effective-date inference from HTTP metadata: **Not performed**
- Human source verification and rewrite: **Required before approval**

## COMNAVRESFOR NOTICE 1001

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

The Reserve Intel monitor detected a newly linked official Navy Reserve guidance document: COMNAVRESFOR NOTICE 1001. The current PDF was re-fetched and matches the fingerprint captured at detection. Human review is required before describing its policy effect.

### Why It Matters

Official Navy Reserve personnel guidance can affect Reserve administration, training, readiness, pay or benefits, retirement, assignments, and related member requirements. The automated detection does not establish which of those areas changed or who is affected. Review the source before making any Salty Dog Bible content or app change.

### Details

Automated evidence verification for COMNAVRESFOR NOTICE 1001: detection kind `new_linked_document`. The official Navy Reserve PDF was re-fetched from https://www.navyreserve.navy.mil/Portals/35/COMNAVRESFOR%20NOTICE%201001.pdf and its SHA-256 fingerprint matched the fingerprint stored with the detected draft. Source-server metadata observed during verification: HTTP Last-Modified: Fri, 20 Nov 2026 18:19:20 GMT; downloaded size: 197,807 bytes. HTTP Last-Modified metadata is not treated as a policy effective date or revision date. The monitor detected a new linked official Navy Reserve guidance PDF. Automated tooling verified the current document fingerprint but has not determined the document's policy effect. Human source review is required.

### Official Source

**Navy Reserve RESFOR Notices**

https://www.navyreserve.navy.mil/Portals/35/COMNAVRESFOR NOTICE 1001.pdf

### Detection Evidence

- Source type: `reserve_guidance`
- Listed date: Not supplied
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Official host verified: Yes
- Detection kind: `new_linked_document`
- Source fingerprint: `c1c4c22015da214e03bc0f04488f6964f2c4257175c7bc14778f547223323f96`

### Navy Reserve Guidance Enrichment Evidence

- Enriched at: 2026-11-20T20:08:12Z
- Document kind: Navy Reserve guidance
- Document identifier: Not supplied
- Source filename: COMNAVRESFOR NOTICE 1001.pdf
- Fetched URL: https://www.navyreserve.navy.mil/Portals/35/COMNAVRESFOR%20NOTICE%201001.pdf
- Detected fingerprint: `c1c4c22015da214e03bc0f04488f6964f2c4257175c7bc14778f547223323f96`
- Observed fingerprint: `c1c4c22015da214e03bc0f04488f6964f2c4257175c7bc14778f547223323f96`
- Fingerprint matched detected version: Yes
- HTTP Last-Modified: Fri, 20 Nov 2026 18:19:20 GMT
- Downloaded size: 197,807 bytes
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
- Extracted text SHA-256: `7b0997727e63aa26ec00e2d3cee20698df59a912df651539e39c8a925e24fd45`
- PDF pages: 6
- Pages with extracted text: 5
- Extracted characters: 9943
- Extracted lines: 255
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

<!-- reserve-intel-article-id: intel-comnavresfor-notice-1001-897de61098 -->
