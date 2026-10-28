"""Host fact-copy proposal only; every proposed token requires target verification."""
import re

STRATEGY = 'FACT_COPY_GREEDY_VERIFY_V1'


def fact_copy_draft(messages):
    if (not isinstance(messages, list) or len(messages) != 2
            or messages[1].get('role') != 'user'
            or not isinstance(messages[1].get('content'), str)
            or not messages[1]['content'].startswith('事实句：\n')):
        raise ValueError('draft requires the selected facts-only prompt')
    facts = messages[1]['content'].removeprefix('事实句：\n')
    from compact_fact_prompt import NO_SPACE_SYSTEM
    if messages[0].get('content')==NO_SPACE_SYSTEM:
        return facts if len(facts.encode('utf-8'))<=1024 else ''
    # The fixed greedy model commonly inserts ASCII spaces around numeric runs.
    # This is a single formatting rule over this request, never an answer lookup.
    proposal = re.sub(r'([0-9]+(?:\.[0-9]+)?)', r' \1 ', facts)
    if len(proposal.encode('utf-8')) > 1024:
        return ''
    return proposal
