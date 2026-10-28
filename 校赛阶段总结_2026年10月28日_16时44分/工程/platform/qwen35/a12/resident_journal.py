"""Bounded internal receipt names and pre-reserved per-event size caps."""
import types
from plm_journal import Journal as Original,need
import plm_journal as original
from plmode_manager import method
from modelpl_derive import Derive
from resident_evidence import ROOT
from resident_policy import IDS
from request_journal_verified import canonical,digest

d=Derive(method(ROOT/'platform/qwen35/a12/plm_journal.py','Journal','receipt'))
d.edit("name in ('app_R0','warm_prefix','app_hit')","name in IDS")
text,RECEIPT_EDITS=d.finish();scope=dict(original.__dict__,IDS=IDS);exec(compile(text,'<resident-bounded-receipt-IDs>','exec'),scope)

class Journal(Original):
    def receipt(self,name,value):return scope['receipt'](self,name,value)
    def append(self,event,**data):
        # Admission reserves this exact upper bound for each possible grant;
        # original total/line bounds, full write/fsync and latch remain below.
        if event=='GRANT':
            sample=dict(schema='PC_PLM_JOURNAL_V1',serial=self.serial+1,previous_sha256=self.chain,epoch=self.epoch,event=event,
                monotonic_ns=2**64-1,**data);sample['sha256']=digest(sample)
            need(len(canonical(sample))+1<=1024,'resident GRANT exceeds pre-reserved record bytes')
        return super().append(event,**data)
