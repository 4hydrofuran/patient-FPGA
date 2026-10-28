"""One-off exact extraction of validated handlers; preserves HealthFence's 2-thread cap."""
import ast
import textwrap
from plm_evidence import ROOT,OUT,sha,save
def main():
    path=ROOT/'platform/qwen35/a12/plm_manager.py';text=path.read_text(encoding='utf-8');tree=ast.parse(text);lines=text.splitlines(True)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Manager');functions={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
    handlers=[]
    for name in ('legacy','private'):
        f=functions['_'+name];nodes=[n for n in ast.walk(f) if isinstance(n,ast.With)]
        assert len(nodes)==1;node=nodes[0];source=''.join(lines[node.lineno-1:node.end_lineno]);body=textwrap.dedent(source)
        handlers.append('    def _'+name+'_message(self,q):\n'+textwrap.indent(body,'        '))
    service='''    def _service(self):
        sockets={self.legacy,self.private};pending=b''
        try:
            while sockets:
                ready,_,_=select.select(list(sockets),[],[],.1)
                for sock in ready:
                    if sock is self.legacy:
                        raw=sock.recv(4097)
                        if not raw:
                            need(self.normal_terminal_requested and not pending,'unexpected/truncated legacy EOF');sockets.remove(sock);continue
                        pending+=raw;need(len(pending)<=4096,'oversize legacy wire')
                        while b'\\n' in pending:
                            line,pending=pending.split(b'\\n',1);self._legacy_message(strict_json(line))
                    else:
                        raw,_,flags,_=sock.recvmsg(8192)
                        if not raw:
                            need(self.normal_terminal_requested,'unexpected private EOF');sockets.remove(sock);continue
                        need(not flags&socket.MSG_TRUNC,'oversize private packet');self._private_message(strict_json(raw))
        except BaseException as exc:self._fail('service: '+str(exc))
'''
    start=functions['_legacy'].lineno-1;end=functions['_private'].end_lineno
    assert ''.join(lines[start:start+1]).strip()=='def _legacy(self):'
    new=''.join(lines[:start])+''.join(handlers)+service+''.join(lines[end:])
    old="self.threads=[threading.Thread(target=self._legacy,name='PLM-legacy',daemon=True),\n            threading.Thread(target=self._private,name='PLM-private',daemon=True),threading.Thread(target=self._stdout,name='PLM-stdout',daemon=True)]"
    replacement="self.threads=[threading.Thread(target=self._service,name='PLM-dual-channel-service',daemon=True),\n            threading.Thread(target=self._stdout,name='PLM-stdout',daemon=True)]"
    assert new.count(old)==1;new=new.replace(old,replacement);ast.parse(new)
    save(OUT/'SERVICE_REFACTOR.json',dict(old_sha256=sha(path),reason='Three consumers exceeded unchanged HealthFence two-thread bound; combine dual channels on one service thread',
        handler_bodies_extracted_exactly=True,HealthFence_modified=False,previous_failure='normal-01/RESULT.json'))
    path.write_text(new,encoding='utf-8')
if __name__=='__main__':main()
