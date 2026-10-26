import hashlib,urllib.request
b=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='6da98c6854573ec667ffc3ef4c005b9ce62b62caba7f1fc664badbebb03f4ad3'
exec(compile(b,'manual_setup','exec'))
