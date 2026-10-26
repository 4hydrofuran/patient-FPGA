import hashlib,urllib.request
b=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='1ce91c71cff6bc844243856309a1cbc8dff97b38e735545b55e26a7480dd3471'
exec(compile(b,'web_setup','exec'))
