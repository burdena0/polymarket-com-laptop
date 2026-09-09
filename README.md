# Polymarket.com weather laptop

A standalone Windows laptop application for public weather-market activity, a local dashboard, and a durable paper simulation journal. This package targets international Polymarket.com public APIs.

## Start

Follow [the laptop installation and startup guide](docs/LAPTOP.md). After setup, run `start.cmd` and visit <http://127.0.0.1:8090/>. Run `stop.cmd` to stop this application.

To view the laptop dashboard from another PC on a trusted local network, see [remote status setup](docs/REMOTE_STATUS.md) and use `start-lan.cmd`.

## Current release

- One process runs the activity observer, simulator, and independent NWS weather model together, sharing one paper cash balance.
- The independent model requires matching NWS CLI settlement rules. Other settlement sources are rejected; the sensitivity model is uncalibrated.
- Public token and condition IDs are verified against market metadata and books.
- A persistent journal prevents duplicate simulated entries and historical replay on startup.
- The dashboard shows its mode, heartbeat, paper positions, and decision reasons.
- The experiment starts with $50 simulated cash and keeps a $40 reserve. The $200 monthly subscription expense is shown separately.

**Paper trading only.** Optional [local account enrollment](docs/ACCOUNT_SETUP.md) encrypts credentials and verifies account reads; it does not enable real orders. A live execution release is not complete. Simulated fills are assumptions based on displayed liquidity; they do not demonstrate executable profitability. Closed-market payouts are not automatically applied.

Run verification with `python -m unittest discover -s tests -v`.

Local configuration and runtime records are excluded from Git. Never add credentials or private keys to this repository.
