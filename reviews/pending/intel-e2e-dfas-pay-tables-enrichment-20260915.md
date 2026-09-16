# Reserve Intel Review

> **Human approval required.** Nothing in this review is live in the app yet.
> Merging this pull request is the approval action. The publish workflow will
> refuse to publish unless every approval checkbox below is checked.

### Review Mode

- Source-specific automation: **DFAS pay-table enrichment applied**
- Automated change attribution: **Not claimed; prior source body is not retained**
- Human source verification and rewrite: **Required before approval**

## E2E TEST — DFAS Military Pay Tables enrichment

| Field | Proposed value |
| --- | --- |
| Category | Pay & Benefits |
| Status | TRACKING |
| Priority | HIGH |
| Service | ALL |
| Reserve status | ALL |
| Training Wing | All |
| Squadron | All |

### Summary

DFAS's official Military Pay Tables source was refetched for this review. The current page matches the fingerprint captured by Reserve Intel monitoring. Human review is still required to identify and verify the specific pay-table change before publication.

### Why It Matters

DFAS publishes authoritative military pay, Reserve drill pay, allowances, and incentive-pay information that may affect Salty Dog Bible pay-related features. The current source contains reserve/pay signals that warrant review, but those signals do not prove which specific value changed.

### Details

Current DFAS source snapshot captured 30 relevant pay-related link(s). Examples: Commissioned Officers; Commissioned Officers Credited with More Than 4 Years of Creditable Service; Warrant Officers; Enlisted Members; Commissioned Officers; Commissioned Officers Credited with More Than 4 Years of Creditable Service; Warrant Officers; Enlisted Members. Signals present on the current page: DRILL PAY, BASIC PAY, AVIATION INCENTIVE PAY, BAS, ALLOWANCE. The current DFAS page is source-grounded and the detected fingerprint was verified when available. The prior page body is not retained, so automation cannot safely identify which specific rate, table, date, or policy text changed. Before approval, open the official source, determine the exact table or rate that changed, verify the effective date and affected audience, and rewrite this article with those verified facts.

### Official Source

**DFAS Military Pay Tables**

https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/

### Detection Evidence

- Source type: `pay_tables`
- Listed date: Not supplied
- Reserve signals: DRILL PAY, BASIC PAY, AVIATION INCENTIVE PAY, BAS, ALLOWANCE
- Official host verified: Yes
- Detection kind: `source_changed_in_place`
- Source fingerprint: `0922d2ad61558a1a60b47dc3662a8e8e2c369173b79ce45e1598ffc7f97a2077`
- Previous fingerprint: `SIMULATED-OLD-DFAS-FINGERPRINT`

### DFAS Pay-Table Enrichment Evidence

- Enriched at: 2026-09-16T00:17:15Z
- Fetched URL: https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/
- Monitor fingerprint matched current source: Yes
- Signals present in current source: DRILL PAY, BASIC PAY, AVIATION INCENTIVE PAY, BAS, ALLOWANCE
- Effective-date text found: None detected
- Posted-date text found: Jan 2026, Dec 2025, Nov 2025, May 2026, Nov. 2025, Sep 2025, Oct. 2019, Aug. 2022, Jan. 2024, Oct. 2021
- Relevant pay-related links captured: 30
- Change attribution: The current DFAS page is source-grounded and the detected fingerprint was verified when available. The prior page body is not retained, so automation cannot safely identify which specific rate, table, date, or policy text changed.

Representative current DFAS links:

- Commissioned Officers — https://www.dfas.mil/Military-Members/payentitlements/Pay-Tables/Basic-Pay/CO/
- Commissioned Officers Credited with More Than 4 Years of Creditable Service — https://www.dfas.mil/Military-Members/payentitlements/Pay-Tables/Basic-Pay/CO_FE/
- Warrant Officers — https://www.dfas.mil/Military-Members/payentitlements/Pay-Tables/Basic-Pay/WO/
- Enlisted Members — https://www.dfas.mil/Military-Members/payentitlements/Pay-Tables/Basic-Pay/EM/
- Commissioned Officers — https://www.dfas.mil/MilitaryMembers/payentitlements/Pay-Tables/Drill-Pay/Drill-Pay-CO/
- Commissioned Officers Credited with More Than 4 Years of Creditable Service — https://www.dfas.mil/MilitaryMembers/payentitlements/Pay-Tables/Drill-Pay/Drill-Pay-CO_FE/
- Warrant Officers — https://www.dfas.mil/MilitaryMembers/payentitlements/Pay-Tables/Drill-Pay/Drill-Pay_WO/
- Enlisted Members — https://www.dfas.mil/MilitaryMembers/payentitlements/Pay-Tables/Drill-Pay/Drill-Pay_E/
- Basic Allowance for Subsistence (BAS) — https://www.dfas.mil/Military-Members/payentitlements/Pay-Tables/bas/
- Standard Initial Clothing Allowances — https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/CMA1
- Clothing Replacement Allowances — https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/CMA2
- Civilian Clothing Allowances - Officer & Enlisted — https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/CMA3

### Potential Salty Dog Bible Impact

> **Informational only.** These tags are an automated first-pass for the reviewer.
> They do not change app behavior, app content, or the live Reserve Intel feed.

- App review recommended: Yes
- Potentially affected features: Drill / Orders, Pay Tracker
- Tagging basis: category: Pay & Benefits, signal: DRILL PAY, keyword: PAY TABLE
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

<!-- reserve-intel-article-id: intel-e2e-dfas-pay-tables-enrichment-20260915 -->
