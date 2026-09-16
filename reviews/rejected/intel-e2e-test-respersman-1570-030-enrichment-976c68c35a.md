# Rejected Reserve Intel Review

- Rejected at: 2026-09-16T02:09:28Z
- Pull request: #8
- Pull request URL: https://github.com/SaltyDogBibleApp/SaltyDogBibleContent/pull/8
- Disposition: Closed without merge

---
# Reserve Intel Review

> **Human approval required.** Nothing in this review is live in the app yet.
> Merging this pull request is the approval action. The publish workflow will
> refuse to publish unless every approval checkbox below is checked.

### Review Mode

- Source-specific automation: **Navy Reserve guidance fingerprint verification applied**
- Automated policy-change attribution: **Not claimed**
- Effective-date inference from HTTP metadata: **Not performed**
- Human source verification and rewrite: **Required before approval**

## E2E TEST — RESPERSMAN 1570-030 enrichment

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

The Reserve Intel monitor detected a new version of RESPERSMAN 1570-030 at its official Navy Reserve PDF URL. The current PDF was re-fetched and matches the fingerprint captured at detection. The exact policy-language changes have not been automatically determined.

### Why It Matters

Official Navy Reserve personnel guidance can affect Reserve administration, training, readiness, pay or benefits, retirement, assignments, and related member requirements. The automated detection does not establish which of those areas changed or who is affected. Review the source before making any Salty Dog Bible content or app change.

### Details

Automated evidence verification for RESPERSMAN 1570-030: detection kind `linked_document_changed`. The official Navy Reserve PDF was re-fetched from https://www.navyreserve.navy.mil/Portals/35/1570-030.pdf and its SHA-256 fingerprint matched the fingerprint stored with the detected draft. Source-server metadata observed during verification: HTTP Last-Modified: Tue, 16 Apr 2024 13:16:27 GMT; downloaded size: 1,689,319 bytes. HTTP Last-Modified metadata is not treated as a policy effective date or revision date. The monitor detected different PDF bytes at an already-known official document URL. The monitor retains document fingerprints, not the prior PDF body, so automated tooling cannot identify which paragraphs, tables, requirements, dates, or policy language changed. Human comparison and source review are required.

### Official Source

**Navy Reserve RESPERSMAN**

https://www.navyreserve.navy.mil/Portals/35/1570-030.pdf

### Detection Evidence

- Source type: `reserve_guidance`
- Listed date: Not supplied
- Reserve signals: None
- Official host verified: Yes
- Detection kind: `linked_document_changed`
- Source fingerprint: `c6b065e4c99c11d919e4f24f44d698021027646a8762d6951453f370d666a9c3`
- Previous fingerprint: `E2E-SIMULATED-OLDER-RESPERSMAN-FINGERPRINT`

### Navy Reserve Guidance Enrichment Evidence

- Enriched at: 2026-09-16T02:07:27Z
- Document kind: RESPERSMAN
- Document identifier: 1570-030
- Source filename: 1570-030.pdf
- Fetched URL: https://www.navyreserve.navy.mil/Portals/35/1570-030.pdf
- Detected fingerprint: `c6b065e4c99c11d919e4f24f44d698021027646a8762d6951453f370d666a9c3`
- Observed fingerprint: `c6b065e4c99c11d919e4f24f44d698021027646a8762d6951453f370d666a9c3`
- Fingerprint matched detected version: Yes
- HTTP Last-Modified: Tue, 16 Apr 2024 13:16:27 GMT
- Downloaded size: 1,689,319 bytes
- ETag: Not supplied
- Automated change attribution claimed: No
- Effective date inferred from HTTP metadata: No
- Change-attribution note: The monitor detected different PDF bytes at an already-known official document URL. The monitor retains document fingerprints, not the prior PDF body, so automated tooling cannot identify which paragraphs, tables, requirements, dates, or policy language changed. Human comparison and source review are required.

> HTTP Last-Modified is source-server metadata only. It is **not** treated
> as the document's policy effective date or authoritative revision date.

### Potential Salty Dog Bible Impact

> **Informational only.** These tags are an automated first-pass for the reviewer.
> They do not change app behavior, app content, or the live Reserve Intel feed.

- App review recommended: Yes
- Potentially affected features: Admin Gouge
- Tagging basis: category: Policy, keyword: RESPERSMAN
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

<!-- reserve-intel-article-id: intel-e2e-test-respersman-1570-030-enrichment-976c68c35a -->
