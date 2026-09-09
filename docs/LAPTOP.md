# Laptop setup

This is the Polymarket.com paper application. It contains an activity copier observer, paper copier, and independent NWS probability strategy, sharing the same cash and position journal. It contains no US account code. Live account enrollment is not implemented; do not supply a private key. The independent model only accepts markets whose rules match NWS CLI station/day settlement; markets using other sources will be rejected.

1. Install Python 3.10 or newer from https://www.python.org/downloads/windows/ and select the option to add Python to PATH. Install Git or download the repository ZIP using GitHub.
2. Open PowerShell. For a cloned repository in Downloads, run:

```powershell
cd "$env:USERPROFILE\Downloads"
git clone https://github.com/burdena0/polymarket-com-laptop.git
cd "$env:USERPROFILE\Downloads\polymarket-com-laptop"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m weather_laptop.app --configure
```

The prompt needs a **public source wallet address**, not a username, seed phrase, US API key, or signing key. It is saved only in local `config.json`. The first successful observation records a baseline; earlier trades are not replayed.

3. Each time you start the application:

```powershell
cd "$env:USERPROFILE\Downloads\polymarket-com-laptop"
.\start.cmd
```

Keep that PowerShell window open. Visit http://127.0.0.1:8090/ on the same computer. Both components share this process and journal. No funding is needed.

4. Stop from another PowerShell window:

```powershell
cd "$env:USERPROFILE\Downloads\polymarket-com-laptop"
.\stop.cmd
```

Wait for the first window to return before starting again. Do not delete lock files or the database. If port 8090 is occupied, stop this application's old instance or use `.\.venv\Scripts\python.exe -m weather_laptop.app --port 8091` and open port 8091.

The dashboard reports **paper** cash and fills. Realized paper P&L changes after simulated sales, and does not include unsold inventory or the separately displayed subscription expense. Automatic settlement is not implemented. Persistent records live under `data/paper-v1`. Preserve them across restarts.

New trades can be skipped for unavailable data, a moved price, insufficient depth, or the market's minimum size. Polling can miss activity; a full 100-record page is reported as incomplete coverage. This is not guaranteed to replicate every source trade.

## Execution integration status

The official international interfaces differ from the US key protocol. The current official SDK also has wallet setup behavior that must be separated from read-only enrollment. No SDK or secret-handling implementation is shipped here yet. The remaining execution work is authentication, independently verified fills and fees, ambiguous-order recovery, holdings reconciliation, and restricted-region checks. Do not treat this paper release as an armed trading bot.
