import hashlib,urllib.request
b=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='8752bbc558fd5f5c7023bb0b45e14f2dcc99a291ec4235f5da0fc4517920d31f'
exec(compile(b,'manual_setup_v4','exec'))
