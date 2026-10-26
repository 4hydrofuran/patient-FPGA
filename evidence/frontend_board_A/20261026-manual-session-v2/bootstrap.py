import hashlib,urllib.request
b=urllib.request.urlopen('http://192.168.2.1:8766/setup.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='14c22327331321b70df84cad3235c9607e87140637376b5450407057927b70a5'
exec(compile(b,'graphical_setup','exec'))
