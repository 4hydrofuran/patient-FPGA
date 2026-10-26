import hashlib,urllib.request
b=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='17e3ca2109f49e3d8963aa486099e69b7ade2be70c238af454a89cff4a9d007c'
exec(compile(b,'manual_setup_v2','exec'))
