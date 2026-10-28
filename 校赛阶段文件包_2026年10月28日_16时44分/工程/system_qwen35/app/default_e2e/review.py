"""Bounded host-only transcript confirmation; never an ASR confidence score.

The console remains the only stdin reader. A worker requests confirmation with
a one-use ticket; old replies cannot confirm a later session's transcript.
"""
import threading,time,uuid

class ReviewGate:
    def __init__(self,notify,timeout_s=60):
        if not 0<timeout_s<=60:raise ValueError('Review timeout must be in (0,60]')
        self.notify=notify;self.timeout_s=timeout_s;self.lock=threading.Lock();self.pending=None;self.last=None

    def confirm(self,ticket,answer):
        if answer not in ('yes','no'):raise ValueError('Use literal yes/no')
        with self.lock:
            p=self.pending
            if p is None or p['ticket']!=ticket or p['answer'] is not None:return False
            p['answer']=answer;p['event'].set();return True

    def request(self,text,cancelled):
        with self.lock:
            if self.pending is not None:raise RuntimeError('Only one transcript review may be pending')
            p={'ticket':uuid.uuid4().hex,'text':text,'answer':None,'event':threading.Event(),'requested_ns':time.monotonic_ns()}
            self.pending=p
        reason='timeout'
        try:
            self.notify({k:p[k] for k in ('ticket','text','requested_ns')})
            deadline=time.monotonic()+self.timeout_s
            while time.monotonic()<deadline:
                if cancelled.is_set():reason='cancelled';break
                if p['event'].wait(min(.05,max(0,deadline-time.monotonic()))):
                    reason='accepted' if p['answer']=='yes' else 'declined';break
            if cancelled.is_set():reason='cancelled'
            return reason=='accepted'
        finally:
            with self.lock:
                self.last={'ticket':p['ticket'],'raw_text':text,'requested_ns':p['requested_ns'],
                           'finished_ns':time.monotonic_ns(),'reason':reason,'approved':reason=='accepted'}
                self.pending=None
