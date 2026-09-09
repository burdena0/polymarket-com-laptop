import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from weather_laptop.account import validate, protect, save, check, client_for


def synthetic():
    return dict(private_key='1'*64,funder='0x'+'2'*40,signature_type=0,
                api_key='test-only',api_secret='test-only',api_passphrase='test-only')


class AccountTests(unittest.TestCase):
    def test_recovery_phrase_rejected(self):
        data=synthetic();data['private_key']='words instead of key'
        with self.assertRaises(ValueError):validate(data)

    @unittest.skipUnless(os.name=='nt','Windows DPAPI')
    def test_encryption_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'key.dpapi';data=synthetic();save(data,path)
            self.assertNotIn(data['private_key'].encode(),path.read_bytes())
            self.assertEqual(json.loads(protect(path.read_bytes(),True)),data)

    @unittest.skipUnless(importlib.util.find_spec('py_clob_client_v2'),'Optional account SDK')
    def test_read_only_mutations_blocked(self):
        client=client_for(synthetic())
        with self.assertRaisesRegex(ValueError,'Read-only'):client._post('https://clob.polymarket.com/order')
        with self.assertRaisesRegex(ValueError,'Read-only'):client._delete('https://clob.polymarket.com/order')

    @unittest.skipUnless(importlib.util.find_spec('py_clob_client_v2'),'Optional account SDK')
    def test_check_output_contains_no_credentials(self):
        class Fake:
            def get_balance_allowance(self,params):return {'balance':'50000000'}
            def get_open_orders(self,only_first_page):
                assert only_first_page
                return []
        output=check(synthetic(),lambda data:Fake())
        self.assertEqual(output['status'],'account_reads_verified')
        self.assertFalse(output['orders_enabled'])
        self.assertNotIn('test-only',json.dumps(output))


if __name__=='__main__':unittest.main()
