"""Prepared typed Board manager; no CLI, owner creation, deploy or enable path.

Only a separately authorized original root ARM64 Owner may instantiate this
class after ordinary baseline acceptance. PC numerical checkpoint hashes are
never used as Board numerical tolerances.
"""
import os
import threading
from pathlib import Path
import resident_manager as cpu
import plmode_manager as base
from plmode_provider import BoardProvider as OriginalBoardProvider
from modelpl_derive import Derive
from resident_evidence import ROOT, read, sha, save
from plm_journal import need
from resident_service import ResidentService


class BoardProvider(OriginalBoardProvider):
    def __init__(self, owner, build):
        need(os.name=='posix' and os.geteuid()==0 and os.uname().machine=='aarch64',
             'resident Board provider requires original actual root ARM64 owner')
        b=read(build)
        need(owner.review.get('resident_model_candidate_approved') is True and
             owner.review.get('resident_policy_sha256')==b['resident_policy_sha256'] and
             b.get('resident_request_limit')==9 and b.get('ordinary_probe_first') is True,
             'fresh explicitly scoped resident policy approval missing')
        super().__init__(owner, build)

    def ready(self, q, m):
        r=super().ready(q,m)
        need(r['plm_control']['request_limit']==9, 'resident Board backend revision differs')
        return r


d=Derive(cpu.init_text)
d.edit("type(provider) is CPUProvider and read(build)['domain']=='PC_REAL_MODEL_PLM_V1'",
       "type(provider) is BoardProvider and read(build)['domain']=='A12_PREPARED_BOARD_MODEL_PLM_V1'")
init_text, INIT_EDITS=d.finish()
init_scope=dict(cpu.init_scope, BoardProvider=BoardProvider)
exec(compile(init_text,'<resident-exact-original-Board-owner>','exec'),init_scope)

d=Derive(base.method(ROOT/'platform/qwen35/a12/plmode_manager.py','Manager','_fixtures'))
d.edit('type(self.provider) is BoardProvider', 'type(self.provider) is ResidentBoardProvider')
fixtures_text, FIXTURE_EDITS=d.finish()
fixture_scope=dict(base.__dict__, ResidentBoardProvider=BoardProvider)
exec(compile(fixtures_text,'<resident-Board-live-source-label>','exec'),fixture_scope)


class Manager(cpu.Manager):
    def __init__(self, build, directory, *, owner, cap=1, coordinator_lock=None, cancel_event=None):
        self.prefix_tokens=34
        self.stream_bytes=self.stream_packets=self.vocab_queries=0
        self.last_private_status=None
        self.current_deadline=None
        self.warm_preparing=False
        provider=BoardProvider(owner,build)
        init_scope['__init__'](self,build,directory,provider=provider,cap=cap,
                               coordinator_lock=coordinator_lock,cancel_event=cancel_event)

    def _fixtures(self):
        return fixture_scope['_fixtures'](self)

    def normal_close(self):
        self.closing=True
        result=cpu.close_scope['normal_close'](self)
        self.provider.native_closed(self)
        self.closed=True
        self.finalized=False
        result.update(status='NATIVE_RESIDENT_BOARD_CONTEXT_CLOSED_OWNER_RETAINED',
                      provider_domain=self.provider.domain, actual_FPGA_calls=None,
                      release_allowed=False)
        return result

    def retain_board_failure(self, reason):
        self._fail(reason)
        self.provider.owner._owned_worker=self
        self.provider.owner.retain_until_finished(reason)


class BoardService(ResidentService):
    """Prepared in-process host API, never selected by CLI/input JSON.

    The original Owner must separately approve a bounded software text test.
    Its PC_TEXT_TEST_ACK remains explicitly no-audio, no medical approval.
    Closing the context never invokes platform restore or Owner.finish.
    """
    def __init__(self, build, directory, *, owner, cap=1):
        need(os.name=='posix' and os.geteuid()==0 and os.uname().machine=='aarch64',
             'resident Board application requires actual original root ARM64 owner')
        super().__init__(build,directory,cap=cap)
        self.owner=owner

    def _initialize_manager(self):
        from livegen_platform import import_original_verified
        original=import_original_verified()
        need(type(self.owner) is original.Owner and
             self.owner.review.get('resident_text_software_test_approved') is True and
             self.owner.review.get('text_test_ack_kind')=='PC_TEXT_TEST_ACK',
             'explicit original Owner synthetic text-test scope missing')
        m=self.manager=Manager.__new__(Manager);m.page=m.p=None
        m.__init__(self.build_path,self.directory,owner=self.owner,cap=self.cap)
        return m

    def finish_original_owner(self):
        need(self.closed and self.manager.closed and not self.failed,
             'verified context close required before original Owner finalization')
        self.manager.finish_original_owner()

    def submit(self, transcript, timeout_s=30):
        response=super().submit(transcript,timeout_s=timeout_s)
        if response.get('type')=='validated_answer':
            response['timing_scope']='BOARD_CANDIDATE_APPLICATION_RETURN_NOT_FINAL_ACCEPTANCE_OR_AUDIO'
        return response
