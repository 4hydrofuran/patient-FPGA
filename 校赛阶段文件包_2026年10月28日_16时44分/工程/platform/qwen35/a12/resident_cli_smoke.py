"""Actual PC CLI host smoke; only synthetic text, no Board/network."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
from resident_evidence import ROOT,OUT,WORK,save


def main():
    os.umask(0o077);folder=OUT/'cli01';folder.mkdir()
    directory=WORK/'cli01';stderr=(folder/'stderr.txt').open('xb')
    p=subprocess.Popen([sys.executable,str(ROOT/'platform/qwen35/a12/resident_cli.py'),
                        '--build',str(OUT/'SERVICE_BUILD-v3.json'),'--directory',str(directory),
                        '--cap','72','--ack-printed-text'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr)
    captured=bytearray();buffer=bytearray();events=[]
    def receive():
        deadline=time.monotonic()+90
        while b'\n' not in buffer:
            remaining=deadline-time.monotonic()
            if remaining<=0 or not select.select([p.stdout],[],[],max(0,remaining))[0]:raise TimeoutError('CLI response not received; retain process state')
            part=os.read(p.stdout.fileno(),32768)
            if not part:raise RuntimeError('CLI ended before expected response')
            captured.extend(part);buffer.extend(part)
            if len(captured)>1024*1024:raise RuntimeError('CLI capture bound')
        line,_,tail=buffer.partition(b'\n');buffer[:]=tail
        q=json.loads(line);events.append(q);return q
    def send(q):p.stdin.write((json.dumps(q,ensure_ascii=False)+'\n').encode());p.stdin.flush()
    try:
        assert receive()['type']=='ready'
        send(dict(op='open_session',case_id='SYN_CP_01'));assert receive()['type']=='session_opened'
        timings=[]
        for i,text in enumerate(('疼痛在什么位置？','刚才呢？')):
            begin=time.monotonic_ns();send(dict(op='submit',transcript=dict(request_id='cli'+str(i+1),text=text,source='typed',final=True)))
            answer=receive();ended=time.monotonic_ns()
            assert answer['type']=='validated_answer' and answer['answer_source']=='MODEL' and answer['tts_ready'] is True
            ack=receive();assert ack['type']=='delivery_ack' and ack['kind']=='PC_TEXT_TEST_ACK' and ack['audio_played'] is False
            timings.append(dict(host_send_to_complete_stdout_s=(ended-begin)/1e9,application_s=answer['input_to_verified_result_s']))
        send(dict(op='close'));assert receive()['type']=='closed';p.stdin.close();p.wait(timeout=30);assert p.returncode==0
        save(folder/'RESULT.json',dict(status='PASS_ACTUAL_PC_CLI_TWO_ANSWERS_AND_HOST_ACK',events=events,timings=timings,
             scope='PC_HOST_PIPE_SEND_TO_COMPLETE_STDOUT_NO_AUDIO_NO_BOARD',BOARD='NOT_TESTED',release_allowed=False))
    finally:
        (folder/'stdout.jsonl').write_bytes(captured);stderr.close()
    print('PASS_ACTUAL_PC_CLI_TWO_ANSWERS_AND_HOST_ACK',flush=True)


if __name__=='__main__':main()
