"""Run actual worker/client with non-speech WAV; no real ASR/TTS claim."""
import hashlib
import json
import sys
import tempfile
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from voicec.client import Client
from voicec.audio import inspect_wav
from voicec.metrics import timing


def main():
    evidence = ROOT / 'evidence/c00'
    evidence.mkdir(parents=True, exist_ok=True)
    trace = []
    with tempfile.TemporaryDirectory(prefix='voice-c00-') as tmp:
        spool = Path(tmp)
        (spool / 'demo').mkdir()
        silence = spool / 'demo/silence.wav'
        with wave.open(str(silence), 'wb') as w:
            w.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            w.writeframes(b'\0\0' * 3200)
        with Client(spool, contract_tone=True) as c:
            def call(op, **fields):
                start = time.perf_counter()
                rid = c.send(op, **fields)
                result = c.receive(rid)
                trace.append(dict(op=op, request_id=rid, result=result,
                                  client_elapsed_ms=(time.perf_counter() - start) * 1000))
                return result
            hello = call('hello')
            assert hello['execution_kind'] == 'CONTRACT_TEST'
            asr = call('transcribe', session_id='demo', language='zh', wav_path='demo/silence.wav')
            assert asr['type'] == 'error' and asr['text'] is None and asr['code'] == 'MODEL_NOT_CONFIGURED'
            tts = call('synthesize', session_id='demo', text='这是非语音协议测试。', output_dir='demo/out')
            assert tts['output_kind'] == 'NON_SPEECH_TEST_TONE'
            info = inspect_wav(spool / tts['wav_path'])
            tone_timing = timing(tts['compute_ms'], info['audio_duration_ms'], tts['ready_ms'],
                                 tts['memory']['peak_rss_bytes'])
            tone_timing['scope'] = 'NON_SPEECH_TONE_PROTOCOL_OVERHEAD_NOT_TTS_PERFORMANCE'
            reset = call('reset', session_id='demo')
            assert reset['epoch'] == 1 and not (spool / tts['wav_path']).exists()
            assert silence.exists()  # Caller input is never deleted by reset.
            final = call('hello')
            assert final['capabilities']['real_asr'] is False
    report = dict(status='PASS_CONTRACT_TEST_ONLY', worker_process_persistent=True,
        actual_asr='NOT_TESTED', actual_tts='NOT_TESTED', real_recordings=0,
        smoke_input_kind='GENERATED_SILENCE_PCM16_NOT_SPEECH',
        smoke_input_sha256=asr['audio_sha256'],
        output_kind='NON_SPEECH_TEST_TONE', tone_measurement=tone_timing,
        real_cer=None, real_asr_rtf=None, real_tts_rtf=None,
        intelligibility=None, audible_latency_ms=None, board='NOT_TESTED')
    (evidence / 'contract_demo.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (evidence / 'protocol_trace.jsonl').write_text('\n'.join(json.dumps(t, ensure_ascii=False) for t in trace) + '\n', encoding='utf-8')
    print('PASS_CONTRACT_TEST_ONLY: persistent worker, valid WAV checks, synthetic tone and owned-file reset; no speech engines.')


if __name__ == '__main__':
    main()
