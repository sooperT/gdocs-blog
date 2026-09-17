# Product Manager Simulation 2008 — v0.1

Minimal, single-file prototype. No deps. Open `index.html` in a browser.

## What’s implemented
- Continuous flow of “kittens” drifting left-to-right.
- Simple terrain tiles: ramp (friction↓), toy (activation/happiness↑), pond (loyalty/referrals), billboard (ads, acquisition+, happiness−), pit (churn).
- Price & release sliders, pause/reset.
- Finance tick: MRR accrues from premium cats; base burn and infra cost reduce cash.
- Referrals from happy, activated cats near a pond.
- Basic UI metrics.

## How to play
- Adjust *Price* and *Release rate*.
- Place tiles with the toolbar (costs cash). Smooth the early path, add a toy to activate, a pond to compound.
- Watch MRR and cash. Avoid pits and billboard overuse to keep happiness up.

## Next steps
- Tech-debt & maintenance/QA allocation.
- Velocity vs burn trade-off.
- Random “exec dog” events.
- Proper NRR and cohort math.
- Save/load.
