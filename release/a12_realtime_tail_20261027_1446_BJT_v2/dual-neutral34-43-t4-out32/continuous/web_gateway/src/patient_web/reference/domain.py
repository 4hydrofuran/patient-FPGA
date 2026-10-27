"""Trusted case storage; requests cannot choose paths or modify the rubric."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math

ROOT=Path(__file__).resolve().parents[1]
CASE_DIR=ROOT/'cases'
SLOTS=('location','quality','onset','duration','severity','radiation','trigger','relief','dyspnea','allergy','medications')

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

@dataclass(frozen=True)
class Fact:
    slot: str
    status: str
    value: object
    unit: str|None
    time_scope: str
    polarity: str
    disclose: str

@dataclass(frozen=True)
class Case:
    case_id: str
    version: str
    review_status: str
    facts: tuple
    sha256: str
    def fact(self,slot):
        return next((f for f in self.facts if f.slot==slot),Fact(slot,'unknown',None,None,'unspecified','unknown','on_slot'))

def validate_case(x):
    if not isinstance(x,dict):raise ValueError('Case must be an object')
    expected={'case_id','version','synthetic','review_status','provenance','rubric_version','unknown_policy','forbidden','facts'}
    if set(x)!=expected or x['synthetic'] is not True:raise ValueError('Invalid synthetic case envelope')
    if x['case_id'] not in ('SYN_CP_01','SYN_CP_02','SYN_CP_03'):raise ValueError('Unknown case ID')
    if x['review_status']!='PENDING_TEACHER_REVIEW':raise ValueError('No approved release supported by this draft build')
    if not isinstance(x['version'],str) or not x['version'] or not isinstance(x['provenance'],str):raise ValueError('Version/provenance')
    if not isinstance(x['forbidden'],list) or not all(isinstance(v,str) for v in x['forbidden']):raise ValueError('Forbidden purposes')
    if x['rubric_version']!='coverage-v1-draft' or x['unknown_policy']!='explicit_unknown-v1-draft':raise ValueError('Unknown policy')
    if not isinstance(x['facts'],list) or not x['facts']:raise ValueError('Missing facts')
    seen=set()
    for f in x['facts']:
        if not isinstance(f,dict):raise ValueError('Fact must be an object')
        if set(f)!={'slot','status','value','unit','time_scope','polarity','disclose'}:raise ValueError('Fact fields')
        if f['slot'] not in SLOTS or f['slot'] in seen:raise ValueError('Duplicate/unknown slot')
        seen.add(f['slot'])
        if f['disclose']!='on_slot' or not isinstance(f['time_scope'],str):raise ValueError('Disclosure/time scope')
        if f['status']=='unknown':
            if f['value'] is not None or f['unit'] is not None or f['polarity']!='unknown':raise ValueError('Missing is not negative')
        elif f['status']=='known':
            slot=f['slot'];value=f['value']
            if slot in ('onset','duration','severity'):
                if type(value) is not int or not 0<value<=240:raise ValueError('Numeric value')
                units={'onset':'小时前','duration':'分钟','severity':'分/10分'}
                if f['unit']!=units[slot] or (slot=='severity' and value>10):raise ValueError('Unit/value')
            elif slot=='dyspnea':
                if type(value) is not bool or f['polarity']!=('positive' if value else 'negative'):raise ValueError('Boolean polarity')
            elif not isinstance(value,str) or not value or len(value)>40:raise ValueError('Categorical value')
            if slot not in ('onset','duration','severity') and f['unit'] is not None:raise ValueError('Unexpected unit')
            if slot!='dyspnea' and f['polarity']!='positive':raise ValueError('Known polarity')
        else:raise ValueError('Fact status')
    return x

def load_case(case_id):
    if case_id not in ('SYN_CP_01','SYN_CP_02','SYN_CP_03'):raise ValueError('Unknown case ID')
    path=CASE_DIR/(case_id+'.json')
    if path.is_symlink():raise ValueError('Symlink case refused')
    raw=path.read_bytes();x=validate_case(json.loads(raw.decode('utf-8')))
    if x['case_id']!=case_id:raise ValueError('Case identity mismatch')
    return Case(x['case_id'],x['version'],x['review_status'],tuple(Fact(**f) for f in x['facts']),hashlib.sha256(raw).hexdigest())

@dataclass(frozen=True)
class Transcript:
    request_id: str
    text: str
    confidence: float|None
    source: str
    start_ms: int|None
    end_ms: int|None
    @classmethod
    def parse(cls,x):
        if not isinstance(x,dict):raise ValueError('Transcript must be an object')
        allowed={'request_id','text','confidence','source','start_ms','end_ms','final'}
        if set(x)-allowed or x.get('final') is not True:raise ValueError('Only final transcripts; no configuration fields')
        if not isinstance(x.get('request_id'),str) or not 1<=len(x['request_id'])<=64:raise ValueError('request_id')
        if not isinstance(x.get('text'),str) or not 1<=len(x['text'])<=1000:raise ValueError('text length')
        if not x['text'].strip() or any(ord(c)<32 and c not in '\n\t' for c in x['text']):raise ValueError('Empty/control transcript')
        if x.get('source') not in ('typed','asr_final'):raise ValueError('source')
        c=x.get('confidence')
        if c is not None and (type(c) not in (int,float) or not math.isfinite(c) or not 0<=c<=1):raise ValueError('confidence')
        start,end=x.get('start_ms'),x.get('end_ms')
        if (start is None)!=(end is None) or (start is not None and (type(start) is not int or type(end) is not int or start<0 or end<start)):raise ValueError('timestamps')
        return cls(x['request_id'],x['text'],c,x['source'],start,end)
