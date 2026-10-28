"""Reuse the unchanged A06 test runner; configure only its evidence directory."""
from pathlib import Path
import sys
import closeout_csim

closeout_csim.E = Path('/mnt/c/Patientqwen/evidence/A06_acceptance/final-20261004-v1')
sys.argv = [sys.argv[0], '--work', str(Path.cwd() / 'current-source-csim'),
            '--label', 'csim', '--license', '/home/member-a/.Xilinx/kv260-a-rehost-20261004.lic']
raise SystemExit(closeout_csim.main())
