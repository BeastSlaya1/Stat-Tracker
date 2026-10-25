import base64, tempfile, unittest
from pathlib import Path
from unittest.mock import patch, Mock
from wifi_settings import validate, load, save, qr_payload, qr_image
from test_app_integration import app
class WifiSettingsTests(unittest.TestCase):
 def test_saved_credentials_survive_reload(self):
  with tempfile.TemporaryDirectory() as directory, patch('storage._data_dir',return_value=directory):
   first=load();self.assertEqual(load(),first)
   chosen=validate('My match','password123');save(chosen);self.assertEqual(load(),chosen)
 def test_android_names_and_password_limits(self):
  self.assertEqual(validate('My match','password123',True)['ssid'],'DIRECT-ST-My match')
  for name,password in [('x'*33,'password123'),('Match','short')]:
   with self.assertRaises(ValueError):validate(name,password)
 def test_qr_is_png_and_escapes_wifi_separators(self):
  data=validate('SCC;Team','password:123')
  self.assertIn(r'S:SCC\;Team;',qr_payload(data));self.assertIn(r'P:password\:123;',qr_payload(data))
  import struct,zlib
  png=base64.b64decode(qr_image(data).split(',')[1]);self.assertEqual(png[:8],b'\x89PNG\r\n\x1a\n')
  width,height=struct.unpack('!II',png[16:24]);self.assertEqual(width,height)
  offset=8;raw=b''
  while offset<len(png):
   length=struct.unpack('!I',png[offset:offset+4])[0];kind=png[offset+4:offset+8];body=png[offset+8:offset+8+length]
   self.assertEqual(zlib.crc32(kind+body)&0xffffffff,struct.unpack('!I',png[offset+8+length:offset+12+length])[0])
   if kind==b'IDAT':raw+=body
   offset+=length+12
  self.assertEqual(len(zlib.decompress(raw)),height*(width+1))
 def test_native_and_web_use_identical_entry(self):
  for web in (False,True):
   a=app();a.is_web=web;a._open_peer_pairing=Mock();a._open_shared_match();a._open_peer_pairing.assert_called_once()

 def test_windows_helper_receives_saved_unicode_name(self):
  import asyncio
  from wifi_point import WifiPoint
  process=Mock();process.poll.return_value=None;process.stdout.readline.return_value='READY\n'
  with patch('wifi_point.Path.exists',return_value=True),patch('wifi_point.subprocess.Popen',return_value=process) as launch:
   point=WifiPoint();asyncio.run(point.start('Equipe é','stable-pass'))
   self.assertEqual(launch.call_args.kwargs['encoding'],'utf-8')
   process.stdin.write.assert_called_once_with('Equipe é\nstable-pass\n')
   asyncio.run(point.start('Equipe é','stable-pass'));launch.assert_called_once()
   point.stop()
