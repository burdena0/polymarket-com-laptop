# Stop the existing desktop bots later

Run this on the desktop, not the laptop. It requests a graceful stop of the combined weather process and the paper dashboard. It does not cancel existing venue orders, sell positions, remove credentials, or turn off Windows.

```powershell
cd 'C:\Users\gamev\Downloads\supahTrade'
New-Item -ItemType File -Path '.\data\us-weather-combined-v1\STOP' -Force | Out-Null
.\stop-live-paper.cmd
```

Let the processes finish their current requests. Check whether they exited:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'supahtrade\.(combined_weather|paper_service)' } |
  Select-Object ProcessId, CommandLine
```

No matching rows means those processes exited. Do not force-delete a database or lock file. The laptop release is paper-only and is not a live migration of the desktop account journal.
