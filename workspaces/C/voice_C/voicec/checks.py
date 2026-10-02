"""Independent real module smoke cycle; never labeled main-app end-to-end."""
import hashlib
from pathlib import Path
import shutil
import time
from .audio import inspect_wav, read_pcm16


def result(reply):
    if reply.get('type') != 'result':
        raise RuntimeError(str(reply))
    return reply


def real_round(client, spool, source, text):
    spool = Path(spool)
    (spool/'check').mkdir(exist_ok=True)
    caller = spool/'check/caller.bin'
    caller.write_bytes(b'caller-owned-preserve')
    wav = spool/'check/input.wav'
    shutil.copyfile(source, wav)
    info, pcm = read_pcm16(wav, asr=True)
    start = time.perf_counter()
    whole = result(client.call('transcribe', session_id='check', wav_path='check/input.wav', language='zh'))
    whole_wall = (time.perf_counter()-start)*1000
    begin = result(client.call('asr_begin', session_id='check', sample_rate=16000, channels=1, format='pcm_s16le'))
    stream = begin['stream_id']
    for seq, offset in enumerate(range(0, len(pcm), 6400)):
        raw = pcm[offset:offset+6400]
        path = spool/'check/chunk.pcm'; path.write_bytes(raw)
        ack = result(client.call('asr_push', stream_id=stream, seq=seq, pcm_path='check/chunk.pcm', final=False))
        assert ack['consumed'] and ack['chunk_sha256'] == hashlib.sha256(raw).hexdigest()
        path.unlink()
        for event in client.drain_events():
            if event.get('event') == 'partial':
                assert event['display_only'] and event['commit_allowed'] is False
    final = result(client.call('asr_finish', stream_id=stream))
    assert final['final'] and final['commit_allowed'] and final['frames'] == len(pcm)//2
    assert final['pcm_sha256'] == hashlib.sha256(pcm).hexdigest()
    assert whole['text'] == final['text'], 'Whole WAV and stream outputs differ'
    start = time.perf_counter()
    speech = result(client.call('synthesize', session_id='check', text=text, output_dir='check/out'))
    ready = (time.perf_counter()-start)*1000
    output = spool/speech['wav_path']; tts_info = inspect_wav(output)
    assert tts_info['sample_rate'] == 22050 and not tts_info['silent']
    assert speech['text_sha256'] == hashlib.sha256(text.encode()).hexdigest()
    reset = result(client.call('reset', session_id='check'))
    assert not output.exists() and caller.read_bytes() == b'caller-owned-preserve' and wav.is_file()
    wav.unlink(); caller.unlink()
    return dict(status='PASS', input_audio_sha256=info['audio_sha256'], whole=whole,
        streaming=final, tts=speech, whole_client_ms=whole_wall, tts_ready_ms=ready,
        reset_epoch=reset['epoch'], cleanup_pass=True, audible_ms=None,
        scope='MODULE_UNPACED_ENGINEERING_NOT_MAIN_APP_E2E_OR_HUMAN_QUALITY')
