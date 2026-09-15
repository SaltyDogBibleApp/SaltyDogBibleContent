# Reserve Intel Review

> **Human approval required.** Nothing in this review is live in the app yet.
> Merging this pull request is the approval action. The publish workflow will
> refuse to publish unless every approval checkbox below is checked.

### Review Mode

> **Manual source review required.** Automated source-specific enrichment and
> shaping are not currently available for source type `pay_tables`.
> The draft below was created from detection metadata and must be verified
> and rewritten from the official source before approval.

- Source-specific automation: **Not applied**
- Human source verification and rewrite: **Required before approval**

## TEST ONLY — DFAS Pay Tables Review Routing

| Field | Proposed value |
| --- | --- |
| Category | Pay & Benefits |
| Status | TRACKING |
| Priority | NORMAL |
| Service | ALL |
| Reserve status | ALL |
| Training Wing | All |
| Squadron | All |

### Summary

Controlled end-to-end test of the Reserve Intel non-NAVADMIN review workflow.

### Why It Matters

This test verifies that a DFAS pay-table draft is routed to manual human review instead of NAVADMIN enrichment.

### Details

TEST ONLY. This draft exists solely to validate GitHub Review PR automation and must not be published.

### Official Source

**DFAS Military Pay Tables**

https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/

### Detection Evidence

- Source type: `pay_tables`
- Listed date: 09/15/2026
- Reserve signals: DRILL PAY
- Official host verified: Yes

### Potential Salty Dog Bible Impact

> **Informational only.** These tags are an automated first-pass for the reviewer.
> They do not change app behavior, app content, or the live Reserve Intel feed.

- App review recommended: Yes
- Potentially affected features: Pay Tracker
- Tagging basis: controlled end-to-end test
- Note: TEST ONLY. Human review required. Do not publish.

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

<!-- reserve-intel-article-id: intel-e2e-pay-tables-20260915 -->
