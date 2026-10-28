"""Prompt experiments with immutable fact requirements; v4 is the minimal fix."""
from ..domain import digest

def prepare(messages,style):
    marker='\n本轮已核对的事实句（逐句原样说出）：\n'
    prefix,sep,body=messages[1]['content'].partition(marker);facts=body.splitlines() if sep else []
    if style=='short':
        messages=[{'role':'system','content':'你是模拟病人。只原样说完事实句，保留数字、单位、肯否和未知，不添事实、不诊断、不评分。输出1至2句，以句号结束。'},messages[1]]
    elif style in ('facts_v2','facts_v3','facts_v4'):
        if not 1<=len(facts)<=2 or not all(f.endswith('。') for f in facts):raise RuntimeError('Trusted prompt format mismatch')
        if style=='facts_v2':
            messages=[{'role':'system','content':'你是模拟病人。只输出已核对的完整回答，不增删事实，不复述问题，不诊断、不评分。'},
                      {'role':'user','content':prefix+'\n已核对的完整回答：'+''.join(facts)}]
        elif style=='facts_v3':messages=[messages[0],{'role':'user','content':prefix+marker+''.join(facts)}]
        elif len(facts)>1:
            # One sentence, all original relation surfaces; single-fact input is
            # byte-for-byte unchanged. No intent-specific or case-specific branch.
            messages=[messages[0],{'role':'user','content':prefix+marker+'，'.join(f[:-1] for f in facts)+'。'}]
    elif style!='old':raise ValueError('Unknown prompt style')
    return messages,{'style':style,'payload_sha256':digest(messages[1]),'messages_sha256':digest(messages),
        'fact_requirement_sha256':digest(facts),'required_sentence_count':len(facts),'question_payload_sha256':digest(prefix)}
