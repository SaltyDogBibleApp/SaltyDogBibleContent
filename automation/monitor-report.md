# Reserve Intel Monitor Report

Run time: **2026-11-03T00:55:19Z**

## Source check cadence

- Checked this run: 10
- Skipped until configured interval: 1

## New potentially relevant items

### VA claim exam (C&P exam)

- Source: **VA Disability Compensation Rates**
- Type: `va_benefits`
- URL: https://www.va.gov/resources/va-claim-exam/
- Reserve signals: DISABILITY COMPENSATION, COMPENSATION RATE, DEPENDENT, SPECIAL MONTHLY COMPENSATION
- Category hints: VA / Veteran Benefits

**Human review required. Detection does not mean this item should be published.**

## Source-check errors

- **MyNavyHR NAVADMIN** — HTTP Error 403: Forbidden
- **MyNavyHR Reserve Officer Boards** — HTTP Error 403: Forbidden
- **MyNavyHR Reserve Officer Continuation and Retention** — HTTP Error 403: Forbidden
- **MyNavyHR Serving on a Reserve Board** — HTTP Error 403: Forbidden
- **Navy Reserve RESPERSMAN** — HTTP Error 403: Forbidden
- **Navy Reserve RESFOR Notices** — HTTP Error 403: Forbidden
- **DFAS Military Pay Tables** — HTTP Error 403: Forbidden
- **BLS Consumer Price Index** — HTTP Error 403: Forbidden
- **DoD Military Compensation** — HTTP Error 403: Forbidden

## Publishing safety

IT-2D.2 is detection-only. The monitor does **not** edit `reserve-content-feed.json`.
Nothing reaches the app until it is separately reviewed and approved.

