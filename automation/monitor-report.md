# Reserve Intel Monitor Report

Run time: **2026-09-29T22:12:18Z**

## Source check cadence

- Checked this run: 11
- Skipped until configured interval: 0

## New potentially relevant items

### COMNAVRESFORNOTE 1001 SIGNED 23SEP2026

- Source: **Navy Reserve RESFOR Notices**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/COMNAVRESFOR NOTICES/COMNAVRESFORNOTE 1001 SIGNED 23SEP2026.pdf
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, SELRES, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Detection: `new_linked_document`
- Source fingerprint: `0402b7784d8f9660825d2b95d353dccb8d7a0771195856526a50b7917957bd41`

**Human review required. Detection does not mean this item should be published.**

### COMNAVRESFORNOTE 6000 SIGNED 23SEP2026

- Source: **Navy Reserve RESFOR Notices**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/COMNAVRESFOR NOTICES/COMNAVRESFORNOTE 6000 SIGNED 23SEP2026.pdf
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, SELRES, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Detection: `new_linked_document`
- Source fingerprint: `a86b7363f2457f73cc7e7795335235b27ed61b1daec5ddbde031ed93fc5d9712`

**Human review required. Detection does not mean this item should be published.**

### Military Retirement

- Source: **DoD Military Compensation**
- Type: `dod_compensation`
- URL: https://militarypay.defense.gov/Pay/Military-Retirement/
- Reserve signals: BASIC PAY, SPECIAL AND INCENTIVE PAY, ALLOWANCES, CONTINUATION PAY
- Category hints: Pay & Benefits, Retirement, Policy

**Human review required. Detection does not mean this item should be published.**

### Thrift Savings Plan

- Source: **DoD Military Compensation**
- Type: `dod_compensation`
- URL: https://militarypay.defense.gov/Benefits/Thrift-Savings-Plan/
- Reserve signals: BASIC PAY, SPECIAL AND INCENTIVE PAY, ALLOWANCES, CONTINUATION PAY
- Category hints: Pay & Benefits, Retirement, Policy

**Human review required. Detection does not mean this item should be published.**

### Annuity for Certain Military Surviving Spouses

- Source: **DoD Military Compensation**
- Type: `dod_compensation`
- URL: https://militarypay.defense.gov/LinkClick.aspx?fileticket=738oSS1VSXI%3d&tabid=836&portalid=3
- Reserve signals: BASIC PAY, SPECIAL AND INCENTIVE PAY, ALLOWANCES, CONTINUATION PAY
- Category hints: Pay & Benefits, Retirement, Policy

**Human review required. Detection does not mean this item should be published.**

## Publishing safety

IT-2D.2 is detection-only. The monitor does **not** edit `reserve-content-feed.json`.
Nothing reaches the app until it is separately reviewed and approved.

