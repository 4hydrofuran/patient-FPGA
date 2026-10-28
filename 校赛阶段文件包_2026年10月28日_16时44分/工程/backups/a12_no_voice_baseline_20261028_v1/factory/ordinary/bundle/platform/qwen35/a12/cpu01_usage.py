"""Read existing Linux counters at request boundaries, without installing tools."""
from pathlib import Path
import os


def process_usage(pid):
    root=Path('/proc')/str(pid)
    stat=(root/'stat').read_text(encoding='utf-8').rsplit(')',1)[1].split()
    status=dict(line.split(':',1) for line in (root/'status').read_text(encoding='utf-8').splitlines() if ':' in line)
    return dict(clock_ticks_per_second=os.sysconf('SC_CLK_TCK'),process_user_ticks=int(stat[11]),process_system_ticks=int(stat[12]),
        main_thread_voluntary_context_switches=int(status['voluntary_ctxt_switches']),
        main_thread_involuntary_context_switches=int(status['nonvoluntary_ctxt_switches']))
