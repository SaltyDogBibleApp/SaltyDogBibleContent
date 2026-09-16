# Reserve Intel Review

> **Human approval required.** Nothing in this review is live in the app yet.
> Merging this pull request is the approval action. The publish workflow will
> refuse to publish unless every approval checkbox below is checked.

### Review Mode

> **Manual source review required.** Automated source-specific enrichment and
> shaping are not currently available for source type `other`.
> The draft below was created from detection metadata and must be verified
> and rewritten from the official source before approval.

- Source-specific automation: **Not applied**
- Human source verification and rewrite: **Required before approval**

## Dashboard Approve E2E Test

| Field | Proposed value |
| --- | --- |
| Category | Admin |
| Status | TRACKING |
| Priority | NORMAL |
| Service | USN |
| Reserve status | ALL |
| Training Wing | All |
| Squadron | All |

### Summary

Synthetic article used only to test approval from the Reserve Intel Mac dashboard.

### Why It Matters

This verifies the dashboard approval, PR merge, and existing publication workflow end to end.

### Details

Test-only content. It will be removed from the live Reserve Intel feed immediately after the E2E test.

### Official Source

**Synthetic Approve E2E Test Source**

https://example.com/reserve-intel-approve-e2e

### Detection Evidence

- Source type: `other`
- Listed date: Not supplied
- Reserve signals: None
- Official host verified: Yes

### Potential Salty Dog Bible Impact

> **Informational only.** These tags are an automated first-pass for the reviewer.
> They do not change app behavior, app content, or the live Reserve Intel feed.

- App review recommended: No
- Potentially affected features: None identified
- Tagging basis: No specific app-impact match
- Note: Human review is required before making any app change.

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

<!-- reserve-intel-article-id: intel-e2e-dashboard-approve-20260916 -->
