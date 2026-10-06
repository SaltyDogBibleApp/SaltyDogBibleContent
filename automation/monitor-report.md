# Reserve Intel Monitor Report

Run time: **2026-10-06T22:38:03Z**

## Source check cadence

- Checked this run: 7
- Skipped until configured interval: 4

## New potentially relevant items

### DFAS Military Pay Tables — source content changed

- Source: **DFAS Military Pay Tables**
- Type: `pay_tables`
- URL: https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/
- Reserve signals: DRILL PAY, BASIC PAY, AVIATION INCENTIVE PAY, BAS, ALLOWANCE
- Category hints: Pay & Benefits
- Detection: `source_changed_in_place`
- Source fingerprint: `9dac21aa967bdcd7d767845fac8ab2bab7d37b19683d3d8a2a4ff7d559a456b0`
- Previous fingerprint: `0922d2ad61558a1a60b47dc3662a8e8e2c369173b79ce45e1598ffc7f97a2077`

**Human review required. Detection does not mean this item should be published.**

## Official sources changed in place

- **DFAS Military Pay Tables** — https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/

These pages changed without exposing a clean new linked item. Review the official source before drafting Intel.

## Publishing safety

IT-2D.2 is detection-only. The monitor does **not** edit `reserve-content-feed.json`.
Nothing reaches the app until it is separately reviewed and approved.

