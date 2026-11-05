# Reserve Intel Monitor Report

Run time: **2026-11-05T19:53:50Z**

## Source check cadence

- Checked this run: 10
- Skipped until configured interval: 1

## New potentially relevant items

### NOTICE OF CONVENING FY-28 NAVY RESERVE LINE REAR ADMIRAL AND REAR ADMIRAL (LOWER HALF) PROMOTION SELECTION BOARDS

- Source: **MyNavyHR NAVADMIN**
- Type: `navadmin`
- URL: https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/NAV2026/NAV26263.pdf?ver=BglW3Xyd3ffxvpp-16Htrg%3d%3d
- Reserve signals: RESERVE
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Listed date: 11/02/2026

**Human review required. Detection does not mean this item should be published.**

### ANNUAL CALL FOR APPLICATIONS FROM QUALIFIED NAVY PERSONNEL FOR THE SYRACUSE UNIVERSITY ADVANCED MILITARY VISUAL JOURNALISM TRAINING PROGRAM 2027

- Source: **MyNavyHR NAVADMIN**
- Type: `navadmin`
- URL: https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/NAV2026/NAV26262.pdf?ver=cmyTKoyqq5PpwVo2iCNEkw%3d%3d
- Reserve signals: TAR
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Listed date: 11/02/2026

**Human review required. Detection does not mean this item should be published.**

### ADJUSTEMENT OF THE CRYPTOLOGIC TECHNICIAN-MAINTENANCE RATING TO THE RESERVE COMPONENT

- Source: **MyNavyHR NAVADMIN**
- Type: `navadmin`
- URL: https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/NAV2026/NAV26261.pdf?ver=I5FOmdCQLQELgSAiiix0mA%3d%3d
- Reserve signals: RESERVE
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Listed date: 11/02/2026

**Human review required. Detection does not mean this item should be published.**

### 1000.1G (s)

- Source: **Navy Reserve RESFOR Notices**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/1000.1G (s).pdf
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Detection: `new_linked_document`
- Source fingerprint: `75e5606260995b0f9f4dd058c51e4d4a7fcc1942932e78ad84a190b02a3f8f4f`

**Human review required. Detection does not mean this item should be published.**

### CNRFCNOTE 5050 - 2026 HOLIDAY PARTY updated (COS signed)

- Source: **Navy Reserve RESFOR Notices**
- Type: `reserve_guidance`
- URL: https://www.navyreserve.navy.mil/Portals/35/CNRFCNOTE 5050 - 2026 HOLIDAY PARTY updated (COS signed).pdf
- Reserve signals: INACTIVE DUTY TRAINING, DRILL, TRAVEL REIMBURSEMENT, SELECTED RESERVE, ACTIVE DUTY TRAINING, RECRUITING, RETENTION, INCENTIVE, APPLY, NATIONAL COMMAND, SENIOR OFFICER, BILLET SCREENING
- Category hints: Policy, Training & Readiness, Admin, Pay & Benefits
- Detection: `new_linked_document`
- Source fingerprint: `4bfffbf4041366cf937051db7a6e2a87c3375863b9d49cd08c86d4294a0d4468`

**Human review required. Detection does not mean this item should be published.**

### DFAS Military Pay Tables — source content changed

- Source: **DFAS Military Pay Tables**
- Type: `pay_tables`
- URL: https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/
- Reserve signals: DRILL PAY, BASIC PAY, AVIATION INCENTIVE PAY, BAS, ALLOWANCE
- Category hints: Pay & Benefits
- Detection: `source_changed_in_place`
- Source fingerprint: `bd45a1347693e3115cf928ce4e596253d42136127ebfb324fd7a78dd1d3a3f64`
- Previous fingerprint: `648891ad72a43fc6173e2b9ac6f82adb6b8f21415fe95b4bb9c394b72891c5a4`

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

