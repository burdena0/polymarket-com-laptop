# Link your international account on the laptop

This links **Polymarket.com** for read-only account verification. It does not turn the paper strategies into live traders. No order, deposit, approval or wallet deployment is performed. Choosing `create` explicitly requests an API key from Polymarket; `existing` and `derive` do not create keys.

## Do I need new keys?

- **Polymarket US keys cannot be reused.** Its key-ID/Ed25519-secret system is different from international CLOB authentication.
- Existing, valid Polymarket.com credentials can be reused on another computer with the matching signer and account wallet. A new laptop alone does not require new API credentials.
- If you already have international credentials but did not save them, the `derive` option retrieves the credentials for the signing key and nonce using the official SDK. It does not create new ones or revoke other keys.
- If no credentials exist, choose `create` in the enrollment prompt. It calls the official SDK's `create_api_key()` once, saves the returned credentials only after account checks pass, and does not revoke another key. If a response is lost or a later check fails, try `derive` with the same nonce to retrieve the issued key rather than repeatedly creating keys. See the [official SDK authentication guide](https://github.com/Polymarket/py-clob-client-v2#authentication).

The pinned compatibility SDK is `py-clob-client-v2==1.1.0`. Polymarket recommends its newer unified SDK for new integrations; this package uses the limited compatibility client to keep enrollment separate from wallet deployment and order methods. A successful account read is not proof that future live execution will work.

## 1. Update and install on the laptop

Sign in to GitHub as an account with access to the private repository, then run in PowerShell:

```powershell
cd "$env:USERPROFILE\Downloads\polymarket-com-laptop"
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e ".[accounts]"
```

If `.venv` is missing, first run `python -m venv .venv`. For the first download, follow [LAPTOP.md](LAPTOP.md).

## 2. Gather the matching international account information

Use your own account, not the public source wallet used for observing activity.

| Prompt | Required information |
|---|---|
| Account wallet | The Polymarket.com wallet holding your funds, shown in your account/profile wallet details |
| Signature type | 0 for an EOA trading directly, 1 for a legacy proxy, 2 for Safe, 3 for a deposit wallet; confirm your actual account type |
| Signing key | The corresponding authorized EVM signer key from your wallet's secure export flow, entered only locally |
| Existing credentials | International CLOB API key, API secret, and API passphrase |
| Derive nonce | The nonce originally used with this signer, usually 0 |

Do not guess that the account wallet equals the signer address: proxy/Safe/deposit wallets differ. If you cannot determine the account type, consult the current official Polymarket wallet documentation before enrollment. A recovery phrase is never accepted. Hardware wallets and browser-only signing are not supported by this local key enrollment command.

## 3. Enroll locally

```powershell
cd "$env:USERPROFILE\Downloads\polymarket-com-laptop"
.\.venv\Scripts\python.exe -m weather_laptop.account --enroll
```

Choose `existing` if you have all three CLOB credentials, `derive` to retrieve already-issued credentials, or `create` to request an API key for this signer and nonce. Secret input is hidden. Do not send keys in chat, screenshots, shell command arguments or GitHub.

The command checks the collateral balance and first page of open orders. Only after both succeed does it encrypt the credentials using Windows DPAPI into `data/connections/international.dpapi`. This file is excluded from Git and bound to your Windows user environment. Enroll again on another laptop rather than copying that encrypted file.

Success prints `account_reads_verified` and `orders_enabled: false`. A failed check leaves any existing saved credentials unchanged. The status file contains only the check result, not secret values.

## 4. Verify later

```powershell
.\.venv\Scripts\python.exe -m weather_laptop.account --check
```

To replace the local connection deliberately:

```powershell
.\.venv\Scripts\python.exe -m weather_laptop.account --enroll --replace
```

Replacing the local file does not revoke the previous API key at Polymarket. This tool does not print saved keys. `account_check_failed` can mean missing SDK dependencies, an incorrect signer/wallet/type, invalid credentials, unavailable network access, or venue rejection. It is not permission to bypass account or geographic restrictions.

## 5. Start the application

```powershell
.\start.cmd
```

The paper account remains separate from the real account balance. Linking credentials does not arm either strategy, copy funds or migrate desktop positions. The remaining live integration requires order lifecycle and settlement reconciliation plus region and allowance checks.
