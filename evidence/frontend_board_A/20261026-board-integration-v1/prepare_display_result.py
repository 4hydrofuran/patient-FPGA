import json,subprocess,html
from pathlib import Path
src=Path('/var/lib/kv260-a12/web-20261026-v1/bundle/run-v1/s2')
dst=Path('/home/ubuntu/snap/firefox/common/pl-result-20261026-v1')
turn=json.loads((src/'web-turn.json').read_text())
report=json.loads((src/'web-report.json').read_text())
def put(name,data):
    code='import sys;from pathlib import Path;p=Path('+repr(str(dst))+');p.mkdir(exist_ok=True);(p/'+repr(name)+').write_bytes(sys.stdin.buffer.read())'
    subprocess.run(['runuser','-u','ubuntu','--','/usr/bin/python3','-c',code],input=data,check=True)
for name in ('browser-answer.png','browser-evaluation.png'):put(name,(src/name).read_bytes())
page='''<!doctype html><meta charset="utf-8"><title>PL result</title>
<style>body{margin:20px;background:#eeeae1;color:#252922;font:22px sans-serif}h1{font-size:28px}img{width:100%;max-width:1024px;display:block;margin:15px 0}small{font-size:16px}a{color:#294b3a}</style>
<h1>'''+'\u771f\u5b9e PL \u8fd0\u884c\u7ed3\u679c'+'''</h1><p>MODEL / FPGA_REAL</p><p>'''+html.escape(turn['question'])+'</p><p>'+html.escape(turn['answer'])+'</p><p>68.36 s | Score 10 / 100</p><small>'+ '\u8fd9\u662f\u5df2\u5b8c\u6210\u7684\u771f\u5b9e\u8fd0\u884c\u8bb0\u5f55\uff0c\u5f53\u524d\u672a\u91cd\u65b0\u63a8\u7406\u3002'+'</small><img src="browser-answer.png"><img src="browser-evaluation.png">'
put('index.html',page.encode('utf-8'))
print('__PL_BEGIN__');print(json.dumps({'result_page':str(dst/'index.html'),'real_result':report['verdict']}));print('__PL_END__')
