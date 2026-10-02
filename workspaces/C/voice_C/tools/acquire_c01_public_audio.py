"""Acquire a small, preselected FLEURS-r development slice with public attribution."""
import hashlib
import argparse
import json
import re
import sys
import tarfile
import urllib.request
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'data/c01_public'
SOURCES=ROOT/'evidence/c01/sources'
REPO='google/fleurs-r'
REVISION='c621c0b7b569dcebcd50273a187a35d1a1fc895f'
sys.path.insert(0,str(ROOT))
from voicec.audio import inspect_wav,read_pcm16,VoiceError
from voicec.prepare_audio import resample_24k_to_16k


def fetch(url):
    request=urllib.request.Request(url, headers={'User-Agent':'voice-C-C01-licensed-public-development-audio'})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-only',action='store_true')
    args=parser.parse_args()
    DEST.mkdir(parents=True,exist_ok=True)
    if (DEST/'manifest.jsonl').exists():
        raise RuntimeError('Public development slice already frozen; do not overwrite')
    metadata=json.loads((SOURCES/'fleurs_r.json').read_text(encoding='utf-8')) if args.local_only else json.loads(fetch(f'https://huggingface.co/api/datasets/{REPO}/revision/{REVISION}'))
    if metadata['sha']!=REVISION: raise ValueError('Dataset revision changed')
    (SOURCES/'fleurs_r.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if metadata.get('cardData',{}).get('license')!='cc-by-4.0':
        raise RuntimeError('Require publisher CC-BY-4.0 declaration')
    revision=metadata['sha']
    base=f'https://huggingface.co/datasets/{REPO}/resolve/{revision}'
    tsv=(SOURCES/'fleurs_r_dev.tsv').read_bytes() if args.local_only else fetch(base+'/data/cmn_hans_cn/dev.tsv')
    (SOURCES/'fleurs_r_dev.tsv').write_bytes(tsv)
    if not args.local_only: (SOURCES/'fleurs_r_card.md').write_bytes(fetch(base+'/README.md'))
    print('Publisher dataset:',REPO,'revision:',revision,'license: cc-by-4.0',flush=True)
    lines=tsv.decode('utf-8').splitlines()
    print('TSV lines:',len(lines),'first column counts:',[len(s.split('\t')) for s in lines[:3]],flush=True)
    # TSV schema verified: sentence id, wav basename, raw transcription, tokenizations, samples, gender.
    rows=[s.split('\t') for s in lines if len(s.split('\t'))==7]
    patterns=dict(negation=r'不|没有|未|无', number=r'[0-9]+(?:\.[0-9]+)?',
        time=r'[0-9一二三四五六七八九十百]+(?:年|月|日|天|小时|分钟)',
        frequency=r'每[天年日月]|经常|频率|每天',
        symptom=r'腹泻|发烧|症状|流感|咳嗽|疼痛|肿胀|感染',
        medical_term=r'病毒|细菌|蛋白质|疫苗')
    chosen=[]
    for kind,pattern in patterns.items():
        matches=[r for r in rows if re.search(pattern,r[2])]
        for row in matches[:2]:
            if row not in chosen: chosen.append(row)
    for row in rows[:4]:
        if row not in chosen: chosen.append(row)
    selection=dict(dataset=REPO,revision=revision,license='cc-by-4.0',split='dev',
        source='data/cmn_hans_cn/dev.tsv',patterns=patterns,
        rule='FIRST_TWO_MATCHES_PER_FIXED_CATEGORY_PLUS_FIRST_FOUR_TSV_ROWS_DEDUPLICATED_BEFORE_ASR',
        rows_with_seven_columns=len(rows),other_lines=len(lines)-len(rows),
        selected_wav_names=[r[1] for r in chosen], selected_count=len(chosen),
        scope='PRESELECTED_PUBLIC_DEVELOPMENT_SLICE_NOT_FULL_FLEURS_OR_STUDENT_TEST')
    (DEST/'selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    archive=ROOT/'assets/public_audio/fleurs_r_cmn_dev.tar.gz'
    archive.parent.mkdir(parents=True,exist_ok=True)
    archive_url=base+'/data/cmn_hans_cn/audio/dev.tar.gz'
    if not archive.exists():
        if args.local_only: raise ValueError('Public archive missing for offline conversion')
        request=urllib.request.Request(archive_url,headers={'User-Agent':'voice-C-C01-licensed-public-development-audio'})
        temporary=archive.with_suffix('.download')
        with urllib.request.urlopen(request,timeout=40) as response,temporary.open('wb') as f:
            total=0
            while chunk:=response.read(1024*1024):
                f.write(chunk);total+=len(chunk)
                if total%(32*1024*1024)<1024*1024: print('Dev archive download bytes:',total,flush=True)
        temporary.replace(archive)
    selected={r[1] for r in chosen}
    extracted={}
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            name=Path(member.name).name
            if name not in selected: continue
            if not member.isfile() or member.size>10*1024*1024 or name in extracted:
                raise ValueError('Invalid/duplicate selected archive member')
            extracted[name]=tar.extractfile(member).read()
    if set(extracted)!=selected: raise ValueError('Selected development audio missing in publisher archive')
    outputs=[]
    for i,row in enumerate(chosen,1):
        filename=row[1]
        if not re.fullmatch(r'[0-9]+\.wav',filename): raise ValueError('Invalid publisher audio basename')
        rid=f'c01.public.{i:03d}'
        directory=DEST/rid;directory.mkdir(exist_ok=True)
        url=archive_url
        original=directory/'source_24k.wav'
        if not original.exists(): original.write_bytes(extracted[filename])
        original_info,pcm=read_pcm16(original)
        if original_info['sample_rate']!=24000: raise ValueError('FLEURS-r source rate differs from inspected 24 kHz')
        path=directory/'in.wav'
        if path.exists() and path.stat().st_size<=44:
            path.rename(directory/'failed_empty_conversion.wav')
        if path.exists() and inspect_wav(path)['sample_rate']!=16000:
            if path.read_bytes()!=extracted[filename]: raise ValueError('Unknown prior audio; cannot replace')
            path.rename(directory/'initial_unconverted_input.wav')
        if not path.exists():
            with wave.open(str(path),'wb') as f:
                f.setparams((1,2,16000,0,'NONE','not compressed'))
                f.writeframes(resample_24k_to_16k(pcm))
        info=inspect_wav(path,asr=True)
        key_items=[dict(kind=kind,text=m.group()) for kind,pattern in patterns.items() for m in re.finditer(pattern,row[2])]
        outputs.append(dict(recording_id=rid,audio_path=f'{rid}/in.wav',**info,
            reference_text=row[2],transcript_status='PUBLISHER_TRANSCRIPT_NOT_LOCALLY_HUMAN_VERIFIED',
            key_items=key_items,source_kind='LICENSED_PUBLIC_RESTORED_SPEECH',split='dev',
            original_audio_path=f'{rid}/source_24k.wav',original_audio_sha256=original_info['audio_sha256'],
            original_sample_rate=24000,restoration='PUBLISHER_MIIPHER_RESTORED_FLEURS_NOT_UNPROCESSED_RECORDING',
            dataset=REPO,revision=revision,source_url=url,publisher_sentence_id=row[0],
            publisher_wav_basename=filename,speaker_id=None,speaker_identity_status='NOT_PROVIDED_IN_TSV',
            consent_reference=None,authorization_status='PUBLIC_LICENSE_CC_BY_4_0',
            license_reference='https://huggingface.co/datasets/google/fleurs-r',
            attribution='Google FLEURS-r; FLEURS authors/contributors; CC BY 4.0',
            changes='LOCAL_BANDLIMITED_24K_TO_16K; NO_CROPPING_OR_DENOISING; PUBLISHER_RESTORED_AUDIO',
            owned_student_recording=False))
        print('Acquired public dev audio:',rid,'ms:',round(info['audio_duration_ms']),flush=True)
    (DEST/'manifest.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in outputs)+'\n',encoding='utf-8')
    (DEST/'archive.lock.json').write_text(json.dumps(dict(source_url=archive_url,revision=revision,
        path=archive.relative_to(ROOT).as_posix(),bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),selected_members=len(outputs)),indent=2)+'\n',encoding='utf-8')
    (DEST/'ATTRIBUTION.md').write_text('# Public development audio attribution\n\nGoogle FLEURS-r / Min Ma and FLEURS-R authors; original FLEURS authors and contributors. CC BY 4.0.\n\nSource: https://huggingface.co/datasets/google/fleurs-r/tree/'+revision+'\n\nLicense: https://creativecommons.org/licenses/by/4.0/\n\nDataset processing: https://www.isca-archive.org/interspeech_2024/ma24c_interspeech.pdf\n\nFLEURS-R contains model-restored read speech at 24 kHz, not unprocessed FLEURS audio or real student speech. Original source WAVs are retained. Local engineering inputs use a windowed-sinc low-pass conversion to 16 kHz without cropping, amplitude adjustment or denoising. Publisher transcripts have not been locally verified by a human. This is a small preselected development slice, not a full FLEURS evaluation. Speaker IDs are unavailable. No final C00 test scripts were accessed.\n',encoding='utf-8')


if __name__=='__main__': main()
