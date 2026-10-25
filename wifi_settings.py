"""Device-only Wi-Fi preferences and interoperable Wi-Fi QR codes."""
import base64,json,secrets,struct,zlib
from pathlib import Path

def validate(ssid,password,android=False):
    ssid=ssid.strip()
    if android and not (len(ssid)>=9 and ssid.startswith('DIRECT-') and ssid[7:9].isascii() and ssid[7:9].isalnum()):ssid='DIRECT-ST-'+ssid
    if not ssid or len(ssid.encode('utf-8'))>32 or any(ord(c)<32 for c in ssid):raise ValueError('Network name must be 1–32 bytes (including Android’s DIRECT-ST- prefix).')
    if not 8<=len(password)<=63 or not password.isascii() or any(ord(c)<32 or ord(c)>126 for c in password):raise ValueError('Password must contain 8–63 printable English letters, numbers or symbols.')
    return {'ssid':ssid,'password':password}

def load(android=False):
    from storage import _data_dir,_atomic_write_json
    path=Path(_data_dir())/'wifi-link.json'
    if path.exists():return validate(**json.loads(path.read_text(encoding='utf-8')),android=android)
    data=validate('StatTracker',secrets.token_hex(8),android)
    _atomic_write_json(str(path),data);return data

def save(data):
    from storage import _data_dir,_atomic_write_json
    _atomic_write_json(str(Path(_data_dir())/'wifi-link.json'),data)

def qr_payload(data):
    def escape(value):
        return ''.join(('\\'+c) if c in '\\;,:"' else c for c in value)
    return 'WIFI:T:WPA;S:'+escape(data['ssid'])+';P:'+escape(data['password'])+';;'

def qr_image(data):
    import qrcode
    qr=qrcode.QRCode(border=4,error_correction=qrcode.constants.ERROR_CORRECT_M);qr.add_data(qr_payload(data));qr.make(fit=True)
    matrix=qr.get_matrix();scale=6;size=len(matrix)*scale
    raw=b''.join((b'\x00'+b''.join((b'\x00' if cell else b'\xff')*scale for cell in row))*scale for row in matrix)
    def chunk(kind,body):return struct.pack('!I',len(body))+kind+body+struct.pack('!I',zlib.crc32(kind+body)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',size,size,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
    return 'data:image/png;base64,'+base64.b64encode(png).decode('ascii')
