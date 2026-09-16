# Reserve Intel Review

> **Human approval required.** Nothing in this review is live in the app yet.
> Merging this pull request is the approval action. The publish workflow will
> refuse to publish unless every approval checkbox below is checked.

### Review Mode

- Source-specific automation: **Navy Reserve guidance fingerprint verification applied**
- Automated policy-change attribution: **Not claimed**
- Effective-date inference from HTTP metadata: **Not performed**
- Human source verification and rewrite: **Required before approval**

## FY26 IDT-R Travel Reimbursement Rules and DTS Requirements

| Field | Proposed value |
| --- | --- |
| Category | Policy |
| Status | EFFECTIVE |
| Priority | NORMAL |
| Service | USN |
| Reserve status | SELRES |
| Training Wing | All |
| Squadron | All |

### Summary

The Navy Reserve’s FY26 Inactive Duty Training Travel Reimbursement (IDT-R) policy provides travel reimbursement for eligible Reserve Sailors who live 150 miles or more from their assigned drill location. Eligible participants may receive reimbursement for up to 12 round trips during FY26, subject to available funding. IDT-R travel must be processed through the Defense Travel System (DTS), and participants must have a Government Travel Charge Card (GTCC).

### Why It Matters

IDT-R can significantly reduce the out-of-pocket cost of traveling long distances to drill, but reimbursement is not automatic. Sailors must meet billet and assignment eligibility requirements, enroll in the program, follow DTS procedures, and document their expenses. The program is discretionary and may be restricted by funding availability.

### Details

COMNAVRESFORNOTE 1570, dated January 15, 2026, establishes the FY26 Navy Reserve IDT-R policy and DTS procedures.
Eligibility generally requires the Sailor to be assigned to an eligible “R”-coded billet, be locally assigned with TRUIC and UMUIC aligned, and have a primary drilling location 150 miles or more from the Sailor’s primary residence. Eligible Sailors must apply through the Navy Reserve IDT-R application process.
IDT-R is considered official travel. Participants are required to have a Government Travel Charge Card (GTCC), and use of a Centrally Billed Account (CBA) is not authorized. A DTS authorization and voucher are required for reimbursement.
Eligible participants may receive reimbursement for up to 12 round trips to their drill site during FY26, subject to the applicable reimbursement limits and available IDT-R funding. The Navy identifies IDT-R as discretionary funding, so reimbursement availability may be restricted by budget constraints.
Reimbursable expenses may include qualifying transportation, lodging, meals, rental vehicle expenses, fuel, and tolls when authorized by the policy. Rental vehicles are reimbursable when they are more advantageous to the government than taxi or rideshare transportation; otherwise reimbursement may be limited to the comparable taxi or rideshare cost.
IDT-R cannot duplicate benefits already provided through IDT meals-in-kind or Berthing for Drilling Reservists. The notice establishes specific meal and lodging reimbursement rules for travel days surrounding the IDT period.
Receipts are required for all IDT-R expenses, including meals, rental cars, fuel, and tolls, even where the normal Joint Travel Regulations receipt threshold would not otherwise require one.
When a DTS authorization cannot be approved before travel and an after-the-fact authorization is required, an IDT-R oral-order confirmation letter must be approved by the NRA commanding officer and uploaded with the DTS authorization and voucher. Failure to provide the required letter results in disapproval of the DTS authorization and voucher.
The notice remains in effect for one year or until revised.

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
