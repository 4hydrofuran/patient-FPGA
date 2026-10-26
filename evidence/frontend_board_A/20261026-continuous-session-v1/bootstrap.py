import hashlib,urllib.request
b=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='fe57ad2abb7a3c729e94c39d68b5a20cbfd170f43be3d14f547662a23a6ae2ad'
exec(compile(b,'continuous_setup','exec'))
