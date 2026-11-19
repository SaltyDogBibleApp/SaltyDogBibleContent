# Reserve Intel Monitor Report

Run time: **2026-11-19T20:30:09Z**

## Source check cadence

- Checked this run: 11
- Skipped until configured interval: 0

## New potentially relevant items

### Flexible Spending Account (FSA)

- Source: **DoD Military Compensation**
- Type: `dod_compensation`
- URL: https://militarypay.defense.gov/Portals/3/Documents/Open_Season_Printout Evergreen.pdf?ver=GYEmyd1Jz2KkjvA4k_fSCw%3d%3d
- Reserve signals: BASIC PAY, SPECIAL AND INCENTIVE PAY, ALLOWANCES
- Category hints: Pay & Benefits, Retirement, Policy

**Human review required. Detection does not mean this item should be published.**

## Source-check errors

- **Navy Reserve RESPERSMAN — RPM Acronyms** — HTTP Error 404: Not Found
- **Navy Reserve RESPERSMAN — RESPERMAN Authorization Letter** — HTTP Error 404: Not Found
- **Navy Reserve RESPERSMAN — RESPERSMAN Table of Contents** — HTTP Error 404: Not Found
- **Navy Reserve RESFOR Notices** — The read operation timed out

## Publishing safety

IT-2D.2 is detection-only. The monitor does **not** edit `reserve-content-feed.json`.
Nothing reaches the app until it is separately reviewed and approved.

