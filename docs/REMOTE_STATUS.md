# View laptop status from your PC

The laptop runs the application. Your PC opens its read-only dashboard. This displays the laptop's paper strategies, not the separate desktop live bots. Account keys and enrollment are not exposed by the web server.

Use a trusted private local network with both computers connected. This HTTP connection is not encrypted; do not use it on public/shared Wi-Fi, port-forward it, or expose it directly to the internet. Different locations require a separately configured secure VPN/tunnel; this release does not provide internet hosting.

On the laptop, after installation and local configuration:

```powershell
cd "$env:USERPROFILE\Downloads\polymarket-com-laptop"
.\start-lan.cmd
```

Do not run `start.cmd` at the same time. A second instance is refused. In another laptop PowerShell window, find the laptop's LAN address:

```powershell
Get-NetIPConfiguration | Where-Object IPv4DefaultGateway | Select-Object InterfaceAlias, @{Name='IPv4';Expression={$_.IPv4Address.IPAddress}}
```

Read your generated monitoring password locally:

```powershell
cd "$env:USERPROFILE\Downloads\polymarket-com-laptop"
Get-Content .\data\monitor-password.txt
```

On the PC open `http://LAPTOP_IPV4:8090/bots` (replace LAPTOP_IPV4 with the address above). At the browser prompt, use username **viewer** and the generated password. This password is only for dashboard viewing; it is not a wallet/API secret.

If Windows Firewall blocks access, on the laptop run the following in **PowerShell as Administrator**, using a trusted network configured as Private:

```powershell
New-NetFirewallRule -DisplayName 'Weather laptop status' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8090 -Profile Private -RemoteAddress LocalSubnet
```

Do not disable the firewall. The rule applies only to the local subnet on Private networks. Router client isolation or a changed DHCP address can also prevent access.

The status page refreshes every five seconds and labels stale reports. The laptop must remain awake, online and running. To stop the laptop application run `stop.cmd`; to return to local-only viewing restart with `start.cmd`.
