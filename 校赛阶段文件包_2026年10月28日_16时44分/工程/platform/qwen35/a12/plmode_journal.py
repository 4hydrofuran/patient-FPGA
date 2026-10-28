"""Frozen bounded journal mechanics, new private mode schema and fault seam."""
import types
from plmode_evidence import ROOT,read,sha
from plm_journal import need
from modelpl_derive import Derive

parent=ROOT/'platform/qwen35/a12/mode_journal.py'
pins={r['path']:r['sha256'] for r in read(ROOT/'evidence/model_pl_A/20261026-mode-control-v1/FINAL_REVIEW.json')['source']}
need(sha(parent)==pins['platform/qwen35/a12/mode_journal.py'],'frozen mode journal changed')
text=parent.read_text(encoding='utf-8');need(text.count('PC_MODE_COORDINATOR_V1')==2,'journal schema anchors differ')
text=text.replace('PC_MODE_COORDINATOR_V1','A12_PLM_MODE_COORDINATOR_V1').replace('PC_MODE_LIVE_SESSION_V1','A12_PLM_MODE_LIVE_SESSION_V1')
d=Derive(text)
d.edit('self._write(self.fd,raw);os.fsync(self.fd);os.fsync(self.parent)',
    "self._write(self.fd,raw)\n            if getattr(self,'inject_event',None)==event:raise OSError('injected mode complete-record fsync failure')\n            os.fsync(self.fd);os.fsync(self.parent)")
text,JOURNAL_EDITS=d.finish();base=types.ModuleType('plmode_frozen_journal');base.__file__=str(parent);exec(compile(text,str(parent)+'#plm-mode','exec'),base.__dict__)
ModeJournal=base.ModeJournal;read_journal=base.read_journal
