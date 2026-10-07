# Reserve Intel Monitor Report

Run time: **2026-10-07T23:02:54Z**

## Source check cadence

- Checked this run: 11
- Skipped until configured interval: 0

## New potentially relevant items

### MILITARY MENTORS FOR UNITED STATES SENATE YOUTH PROGRAM

- Source: **MyNavyHR NAVADMIN**
- Type: `navadmin`
- URL: https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/NAV2026/NAV26235.pdf?ver=nxQvgm3ofRr-XRDxn1gQNw%3d%3d
- Reserve signals: TAR
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Listed date: 10/07/2026

**Human review required. Detection does not mean this item should be published.**

### MILITARY VOTING STAND DOWN

- Source: **MyNavyHR NAVADMIN**
- Type: `navadmin`
- URL: https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/NAV2026/NAV26234.pdf?ver=A3EDXWn5d8vnLDRmFqL9iQ%3d%3d
- Reserve signals: TAR
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Listed date: 10/07/2026

**Human review required. Detection does not mean this item should be published.**

### RPM Acronyms

- Source: **Navy Reserve RESPERSMAN**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/Official RESFOR Guidance/RESPERMAN/Reserve Military Personnel Manual/RPM Acronyms.pdf
- Reserve signals: Curated source change
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits

**Human review required. Detection does not mean this item should be published.**

### RESPERMAN Authorization Letter

- Source: **Navy Reserve RESPERSMAN**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/Official RESFOR Guidance/RESPERMAN/Reserve Military Personnel Manual/RESPERMAN Authorization Letter.pdf
- Reserve signals: Curated source change
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits

**Human review required. Detection does not mean this item should be published.**

### RESPERSMAN Table of Contents

- Source: **Navy Reserve RESPERSMAN**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/Official RESFOR Guidance/RESPERMAN/Reserve Military Personnel Manual/RESPERSMAN Table of Contents.pdf
- Reserve signals: Curated source change
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits

**Human review required. Detection does not mean this item should be published.**

### COMNAVRESFORNOTE 6000 - FY27 SELRES HEALTH PROFESSIONS OFFICERS IN CRITICAL WARTIME SPECIALTIES RECRUITING AND RETENTION INCENTIVES - SIGNED FINAL 2.0

- Source: **Navy Reserve RESFOR Notices**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/Official RESFOR Guidance/N01A Documents/COMNAVRESFOR NOTICES/FY27/COMNAVRESFORNOTE 6000 - FY27 SELRES HEALTH PROFESSIONS OFFICERS IN CRITICAL WARTIME SPECIALTIES RECRUITING AND RETENTION INCENTIVES - SIGNED FINAL 2.0.pdf
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, SELRES, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Detection: `new_linked_document`
- Source fingerprint: `8285455b5e65ba5f3dda92406e597e6bc86dd48b3664c8b61728dc7f2134902d`

**Human review required. Detection does not mean this item should be published.**

### DFAS Military Pay Tables — source content changed

- Source: **DFAS Military Pay Tables**
- Type: `pay_tables`
- URL: https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/
- Reserve signals: DRILL PAY, BASIC PAY, AVIATION INCENTIVE PAY, BAS, ALLOWANCE
- Category hints: Pay & Benefits
- Detection: `source_changed_in_place`
- Source fingerprint: `f8d52ef343e669ce9c48ccec6d42f9b0e0036e99b6582c0519faceb7700b7b2c`
- Previous fingerprint: `9dac21aa967bdcd7d767845fac8ab2bab7d37b19683d3d8a2a4ff7d559a456b0`

**Human review required. Detection does not mean this item should be published.**

### Fiduciary help

- Source: **VA Disability Compensation Rates**
- Type: `va_benefits`
- URL: https://www.va.gov/resources/fiduciary-help/
- Reserve signals: DISABILITY COMPENSATION, COMPENSATION RATE, DEPENDENT, SPECIAL MONTHLY COMPENSATION
- Category hints: VA / Veteran Benefits

**Human review required. Detection does not mean this item should be published.**

## Official sources changed in place

- **DFAS Military Pay Tables** — https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/

These pages changed without exposing a clean new linked item. Review the official source before drafting Intel.

## Source-check errors

- **Navy Reserve RESPERSMAN — RPM Acronyms** — HTTP Error 404: Not Found
- **Navy Reserve RESPERSMAN — RESPERMAN Authorization Letter** — HTTP Error 404: Not Found
- **Navy Reserve RESPERSMAN — RESPERSMAN Table of Contents** — HTTP Error 404: Not Found

## Publishing safety

IT-2D.2 is detection-only. The monitor does **not** edit `reserve-content-feed.json`.
Nothing reaches the app until it is separately reviewed and approved.

