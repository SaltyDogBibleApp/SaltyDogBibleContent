# Reserve Intel Review

> **Human approval required.** Nothing in this review is live in the app yet.
> Merging this pull request is the approval action. The publish workflow will
> refuse to publish unless every approval checkbox below is checked.

### Review Mode

- Source-specific automation: **Navy Reserve guidance fingerprint verification + extracted-text diff applied**
- Automated policy-change attribution: **Not claimed**
- Effective-date inference from HTTP metadata: **Not performed**
- Human source verification and rewrite: **Required before approval**

## RESPERSMAN 1570-030

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

The Reserve Intel monitor detected a new version of RESPERSMAN 1570-030 at its official Navy Reserve PDF URL. The current PDF was re-fetched and matches the fingerprint captured at detection. A normalized extracted-text comparison is available for human review. No automated conclusion has been made about the policy meaning or effect of those differences.

### Why It Matters

Official Navy Reserve personnel guidance can affect Reserve administration, training, readiness, pay or benefits, retirement, assignments, and related member requirements. The automated detection does not establish which of those areas changed or who is affected. Review the source before making any Salty Dog Bible content or app change.

### Details

Automated evidence verification for RESPERSMAN 1570-030: detection kind `linked_document_changed`. The official Navy Reserve PDF was re-fetched from https://www.navyreserve.navy.mil/Portals/35/1570-030.pdf and its SHA-256 fingerprint matched the fingerprint stored with the detected draft. Source-server metadata observed during verification: HTTP Last-Modified: Tue, 16 Apr 2024 13:16:27 GMT; downloaded size: 1,689,319 bytes. Extracted-text comparison: 1 removed line(s), 1 added line(s), 1 change hunk(s). HTTP Last-Modified metadata is not treated as a policy effective date or revision date. Prior and current normalized extracted-text snapshots are available. Automation identified extraction-level additions and removals for human review, but it has not determined the meaning, applicability, or policy effect of those differences. PDF layout/extraction can also create apparent text changes. Human comparison of the official source is required.

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
- Previous fingerprint: `0000000000000000000000000000000000000000000000000000000000000001`

### Navy Reserve Guidance Enrichment Evidence

- Enriched at: 2026-09-16T03:08:22Z
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
- Change-attribution note: Prior and current normalized extracted-text snapshots are available. Automation identified extraction-level additions and removals for human review, but it has not determined the meaning, applicability, or policy effect of those differences. PDF layout/extraction can also create apparent text changes. Human comparison of the official source is required.

> HTTP Last-Modified is source-server metadata only. It is **not** treated
> as the document's policy effective date or authoritative revision date.

### Current PDF Text Extraction

- Snapshot available: Yes
- Extraction status: ok
- Extraction method: pypdf
- Extracted text SHA-256: `57a6727f92504ddcb84ead238277b5d21c39f26d59cc16d734118c0dff3ece56`
- PDF pages: 4
- Pages with extracted text: 4
- Extracted characters: 7055
- Extracted lines: 128
- Extraction truncated by safety limit: No

### Extracted Text Comparison

- Comparison available: Yes
- Policy interpretation claimed: No
- Extracted text changed: Yes
- Previous text SHA-256: `e35f0c226b3c7049899d97fc7391d49ecf837d2c0bf76538085b8f14d64b4e68`
- Current text SHA-256: `57a6727f92504ddcb84ead238277b5d21c39f26d59cc16d734118c0dff3ece56`
- Previous extraction status: ok
- Current extraction status: ok
- Removed extracted lines: 1
- Added extracted lines: 1
- Change hunks detected: 1
- Change hunks shown: 1
- Hunk list truncated: No

> **Extraction-level evidence only.** Differences below identify changes in
> normalized text extracted from the two PDFs. They do not establish
> policy meaning, applicability, effective date, or implementation effect.

#### Extracted change 1

- Diff kind: `replace`
- Previous page: 1
- Current page: 1
- Nearby heading (heuristic): Individual Inactive Duty Trainin2 Record Maintenance

**Removed extracted text**

```text
• Required non-IDT orders to be maintained in the
```

**Added extracted text**

```text
• Removed the requirement for non-IDT orders to be maintained in the
```

> This comparison is based on normalized text extracted from two PDF versions. PDF layout or extraction behavior can create apparent text differences. Human review of the official source is required before describing policy effect.

### Potential Salty Dog Bible Impact

> **Informational only.** These tags are an automated first-pass for the reviewer.
> They do not change app behavior, app content, or the live Reserve Intel feed.

- App review recommended: Yes
- Potentially affected features: Admin Gouge
- Tagging basis: synthetic RESPERSMAN text-diff E2E
- Note: Synthetic test only. Human review required.

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

<!-- reserve-intel-article-id: intel-e2e-test-respersman-text-diff-1570-030-20260915 -->
