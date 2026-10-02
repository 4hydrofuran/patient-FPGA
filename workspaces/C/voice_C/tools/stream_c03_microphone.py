"""Independent Windows microphone client, local streaming ASR, no audio upload."""
import argparse
import array
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from voicec.client import Client
from voicec.microphone import Microphone, WinMM


def require_result(reply):
    if reply.get('type') != 'result':
        raise RuntimeError(json.dumps(reply, ensure_ascii=False))
    return reply


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list-devices', action='store_true', help='Enumerate only; never opens microphone')
    parser.add_argument('--record', action='store_true', help='Authorize this local recording; no raw audio retained')
    parser.add_argument('--device', type=int, default=0)
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--countdown', type=int, default=5)
    parser.add_argument('--output', type=Path, help='New directory for local transcript and diagnostic trace')
    args = parser.parse_args()
    if args.list_devices:
        print(json.dumps(dict(devices=WinMM().devices(), microphone_opened=False), ensure_ascii=False))
        return 0
    if not args.record or args.output is None:
        parser.error('Use --list-devices or explicitly --record --output NEW_DIRECTORY')
    if not 0 <= args.countdown <= 30:
        parser.error('countdown must be 0..30 seconds')
    # Validate before spawning worker or creating files.
    mic = Microphone(device=args.device, seconds=args.seconds)
    devices = mic.backend.devices()
    selected = next((d for d in devices if d['id'] == args.device), None)
    if selected is None:
        parser.error('Requested microphone is not enumerated')
    mic.backend.query(args.device)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(status='STARTING', execution_kind='PC_REAL_MICROPHONE', device=selected,
                  requested_seconds=args.seconds, sample_rate=16000, channels=1, format='pcm_s16le',
                  authorization='CALLER_EXPLICIT_RECORD_FLAG', raw_audio_retained=False,
                  human_reference_text=None, human_cer=None, human_speech_end_latency_ms=None,
                  quality_status='PENDING_HUMAN_REFERENCE', chunks=[], partial_events=[])
    digest = hashlib.sha256()
    peak, squared, clipped, frames = 0, 0, 0, 0
    start_wall = time.perf_counter()
    exit_code = 1
    # Worker import path must work even if launched from another directory.
    os.chdir(ROOT)
    with tempfile.TemporaryDirectory(prefix='voicec-mic-') as temp, (args.output / 'trace.jsonl').open('w', encoding='utf-8') as trace:
        def record(item):
            trace.write(json.dumps(item, ensure_ascii=False) + '\n')
            trace.flush()
        c = None
        try:
            spool = Path(temp)
            (spool / 'microphone').mkdir()
            c = Client(spool, asr_config=ROOT / 'configs/asr.selected.json',
                       stream_config=ROOT / 'configs/stream.selected.json', response_timeout=15,
                       trace_callback=record)
            report['hello'] = require_result(c.call('hello'))
            print(f'Microphone ready: {selected["name"]}; recording {args.seconds:g} seconds in {args.countdown} seconds.', flush=True)
            # Countdown before begin, so the worker idle lease cannot expire.
            time.sleep(args.countdown)
            begin = require_result(c.call('asr_begin', session_id='microphone', sample_rate=16000,
                                          channels=1, format='pcm_s16le'))
            report['begin'] = begin
            stream = begin['stream_id']
            print('RECORDING: speak now. Audio stays local and is deleted after acknowledgement.', flush=True)
            with mic:
                for item in mic:
                    raw, seq = item['pcm'], item['seq']
                    path = spool / 'microphone' / 'chunk.pcm'
                    path.write_bytes(raw)
                    sent = time.perf_counter()
                    ack = require_result(c.call('asr_push', stream_id=stream, seq=seq, pcm_path='microphone/chunk.pcm', final=False))
                    end = time.perf_counter()
                    chunk_hash = hashlib.sha256(raw).hexdigest()
                    if not ack.get('consumed') or ack.get('chunk_sha256') != chunk_hash or ack.get('chunk_frames') != len(raw) // 2:
                        raise RuntimeError('Microphone chunk acknowledgement/hash mismatch')
                    path.unlink()  # Only after consumption is acknowledged.
                    digest.update(raw)
                    samples = array.array('h', raw)
                    if sys.byteorder != 'little':
                        samples.byteswap()
                    frames += len(samples)
                    peak = max(peak, max(abs(x) for x in samples))
                    squared += sum(x * x for x in samples)
                    clipped += sum(x in (-32768, 32767) for x in samples)
                    report['chunks'].append(dict(seq=seq, frames=len(samples), sha256=chunk_hash,
                        available_monotonic=item['available_monotonic'], sent_monotonic=sent,
                        capture_to_send_ms=(sent - item['available_monotonic']) * 1000,
                        ack_ms=(end - sent) * 1000, response=ack))
                    for event in c.drain_events():
                        report['partial_events'].append(event)
                        if 'text' in event:
                            print('partial: ' + event['text'], flush=True)
            report['capture'] = dict(mic.stats)
            if frames != mic.target_frames or digest.hexdigest() != mic.stats.get('pcm_sha256'):
                raise RuntimeError('Captured and acknowledged PCM do not match')
            finish_start = time.perf_counter()
            final = require_result(c.call('asr_finish', stream_id=stream))
            report['finish_to_final_ms'] = (time.perf_counter() - finish_start) * 1000
            if not final.get('final') or final.get('frames') != frames or final.get('pcm_sha256') != digest.hexdigest():
                raise RuntimeError('Final result does not match acknowledged microphone PCM')
            report.update(status='PASS_CAPTURE_AND_PROTOCOL', final=final)
            exit_code = 0
        except (Exception, KeyboardInterrupt) as exc:
            report.update(status='FAILED', error=dict(type=type(exc).__name__, message=str(exc)))
            print('Microphone run failed: ' + str(exc), file=sys.stderr, flush=True)
            if c and report.get('begin'):
                try:
                    report['reset_after_failure'] = c.call('reset', session_id='microphone')
                except Exception as reset_error:
                    report['reset_error'] = str(reset_error)
        finally:
            try:
                mic.close()
            except Exception as exc:
                report.update(status='FAILED', close_error=str(exc))
                exit_code = 1
            if c:
                try:
                    c.close()
                except Exception as exc:
                    report.update(status='FAILED', worker_close_error=str(exc))
                    exit_code = 1
                (args.output / 'stderr.log').write_text(''.join(c.stderr), encoding='utf-8')
                report['worker_exit_code'] = c.process.poll()
            report['capture'] = dict(mic.stats)
            report['audio_stats'] = dict(frames=frames, duration_ms=frames / 16, peak=peak,
                rms=math.sqrt(squared / frames) if frames else None, clipped_samples=clipped,
                digital_silence=peak == 0, pcm_sha256=digest.hexdigest())
            report['wall_ms'] = (time.perf_counter() - start_wall) * 1000
            (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Temporary spool removed, including every unacknowledged chunk on failure.
    print(json.dumps(dict(status=report['status'], frames=frames, peak=peak,
        raw_audio_retained=False, device_released=mic.stats['released'],
        text=report.get('final', {}).get('text'), report_path=str(args.output / 'report.json')), ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
