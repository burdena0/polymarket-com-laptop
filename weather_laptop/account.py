"""User-operated international account enrollment; no order methods exposed."""
import argparse
import ctypes
from ctypes import wintypes
from dataclasses import asdict
from getpass import getpass
import json
import logging
import os
from pathlib import Path
import re
import time
import warnings
from getpass import GetPassWarning
from .core import number, wallet

STORE = Path('data/connections/international.dpapi')
STATUS = Path('data/connections/status.json')


def protect(data, decrypt=False):
    if os.name != 'nt':
        raise ValueError('Encrypted enrollment requires Windows')
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_byte))]
    buffer = ctypes.create_string_buffer(data)
    incoming = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    outgoing = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise ValueError('Windows credential protection failed; enroll on this laptop')
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        kernel = ctypes.WinDLL('kernel32')
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(ctypes.cast(outgoing.data, ctypes.c_void_p))


def validate(data):
    wallet(data['funder'])
    if not re.fullmatch(r'(0x)?[a-fA-F0-9]{64}', data['private_key']):
        raise ValueError('Expected a single EVM signing key, not a recovery phrase')
    if type(data['signature_type']) is not int or data['signature_type'] not in (0,1,2,3):
        raise ValueError('Unsupported wallet signature type')
    for key in ('api_key','api_secret','api_passphrase'):
        if not isinstance(data[key],str) or not data[key].strip():
            raise ValueError('All three international API credential fields are required')


def client_for(data):
    from py_clob_client_v2 import ClobClient, ApiCreds
    class ReadOnlyClient(ClobClient):
        def _post(self, *args, **kwargs):
            raise ValueError('Read-only enrollment cannot post orders or other mutations')
        def _delete(self, *args, **kwargs):
            raise ValueError('Read-only enrollment cannot delete or cancel')
    return ReadOnlyClient('https://clob.polymarket.com',137,key=data['private_key'],
        funder=data['funder'],signature_type=data['signature_type'],
        creds=ApiCreds(data['api_key'],data['api_secret'],data['api_passphrase']),retry_on_error=False)


def check(data, factory=client_for):
    validate(data)
    client = factory(data)
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    result = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    balance = number(result['balance'])
    if balance < 0:
        raise ValueError('Invalid collateral balance')
    orders = client.get_open_orders(only_first_page=True)
    if not isinstance(orders,list):
        raise ValueError('Unexpected open-order response')
    return {'status':'account_reads_verified','checked_at':time.time(),'orders_enabled':False,
            'collateral_balance_base_units':str(balance),'open_orders_first_page':len(orders),
            'order_history_complete':False,
            'scope':'Credentialed balance and first-page open-order reads only. Not signing authority, allowance, or execution verification.'}


def save(data, path=STORE):
    validate(data)
    encrypted = protect(json.dumps(data).encode())
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_bytes(encrypted)
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--enroll',action='store_true')
    actions.add_argument('--check',action='store_true')
    parser.add_argument('--replace',action='store_true',help='Replace the saved local connection after verification')
    args = parser.parse_args()
    # SDK request errors must never dump account response bodies into the terminal.
    logging.disable(logging.CRITICAL)
    warnings.simplefilter('error',GetPassWarning)
    try:
        if args.enroll:
            if STORE.exists() and not args.replace:
                raise ValueError('Already enrolled. Use --check, or --enroll --replace to replace locally.')
            print('Polymarket.com only. Enter secrets here; input is hidden. Never paste recovery phrases.')
            data = {'funder':wallet(input('Your Polymarket.com account wallet address: ').strip()),
                    'signature_type':int(input('Wallet signature type (0 EOA, 1 proxy, 2 Safe, 3 deposit wallet): ').strip()),
                    'private_key':getpass('Signing private key: ').strip()}
            mode = input('Credentials: existing, derive, or create (issues an API key): ').strip().lower()
            if mode in ('derive','create'):
                from py_clob_client_v2 import ClobClient
                nonce=int(input('Existing credential nonce (usually 0): ').strip() or '0')
                if nonce<0:raise ValueError('Nonce must be nonnegative')
                client=ClobClient('https://clob.polymarket.com',137,key=data['private_key'],retry_on_error=False)
                data.update(asdict(client.derive_api_key(nonce=nonce) if mode == 'derive' else client.create_api_key(nonce=nonce)))
            elif mode == 'existing':
                data.update(api_key=getpass('CLOB API key: ').strip(),api_secret=getpass('CLOB API secret: ').strip(),
                            api_passphrase=getpass('CLOB API passphrase: ').strip())
            else:
                raise ValueError('Choose existing or derive; no keys were created')
        else:
            data=json.loads(protect(STORE.read_bytes(),True))
        result=check(data)
        if args.enroll:save(data)
        STATUS.parent.mkdir(parents=True,exist_ok=True)
        STATUS.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    except Exception as exc:
        # Do not print arbitrary exception text containing SDK response material.
        result={'status':'account_check_failed','checked_at':time.time(),'orders_enabled':False,
                'error_type':type(exc).__name__, 'next_step':'Check installation, account wallet/type and credentials. Saved keys were not replaced. See docs/ACCOUNT_SETUP.md.'}
        STATUS.parent.mkdir(parents=True,exist_ok=True)
        STATUS.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
        raise SystemExit(1)


if __name__=='__main__':main()
