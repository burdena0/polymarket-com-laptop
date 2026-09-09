import base64
from pathlib import Path
import tempfile
import unittest
from weather_laptop.remote import authorized,password

class RemoteTests(unittest.TestCase):
 def test_authentication_required(self):
  key='test-password'*4
  header='Basic '+base64.b64encode(('viewer:'+key).encode()).decode()
  self.assertTrue(authorized(header,key,'192.168.1.20'))
  self.assertFalse(authorized(header,key,'8.8.8.8'))
  self.assertFalse(authorized(None,key,'192.168.1.20'))
  self.assertFalse(authorized('Basic !!!',key,'127.0.0.1'))
  self.assertFalse(authorized(header,'different','192.168.1.20'))
 def test_password_persisted(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'password.txt';first=password(path)
   self.assertGreaterEqual(len(first),32);self.assertEqual(first,password(path))
