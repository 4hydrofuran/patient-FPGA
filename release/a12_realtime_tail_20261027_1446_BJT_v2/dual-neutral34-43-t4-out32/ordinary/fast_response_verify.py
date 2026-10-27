"""Verify offline PC candidates, or explicitly enter a fresh original-Owner BOARD window."""
import argparse
import json
from pathlib import Path
import sys
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain',choices=('PC','BOARD'),required=True)
    parser.add_argument('--bundle',type=Path,required=True,help='prepared profile root containing ordinary/continuous')
    parser.add_argument('--suite',choices=('package','model','ordinary','web'),default='package')
    parser.add_argument('--output',type=Path,help='new evidence directory for a PC attempt')
    parser.add_argument('--pc-binary',type=Path)
    parser.add_argument('--pc-library-dir',type=Path)
    parser.add_argument('--model',type=Path)
    parser.add_argument('--execute-board',action='store_true')
    parser.add_argument('--window-id')
    args=parser.parse_args()
    from fast_response_prepare_support import verify_package
    metadata=verify_package(args.bundle)
    if args.domain=='BOARD':
        if args.suite not in ('ordinary','web') or not args.execute_board or not args.window_id:
            parser.error('BOARD requires --suite ordinary|web --execute-board --window-id <fresh-id>')
        window=args.bundle/('ordinary' if args.suite=='ordinary' else 'continuous')
        sys.path.insert(0,str(window.resolve()))
        from fast_response_entry import run_board
        run_board(window,'ordinary' if args.suite=='ordinary' else 'continuous',args.window_id)
    elif args.suite=='package':
        checks=[]
        for kind in ('ordinary','continuous'):
            r=subprocess.run([sys.executable,'-B',str(args.bundle/kind/'fast_response_preflight.py'),
                              '--window',str(args.bundle/kind)],capture_output=True,text=True)
            if r.returncode:raise RuntimeError('offline dependency/profile check failed: '+r.stderr)
            checks.append(json.loads(r.stdout))
        print(json.dumps(dict(status='PASS_OFFLINE_PACKAGE',files=len(metadata['files']),
                             checks=checks,BOARD='NOT_TESTED'),indent=2))
    elif args.suite=='model':
        if not args.output:parser.error('PC model requires --output <new-attempt-directory>')
        from fast_response_pc import verify_model
        print(json.dumps(verify_model(args),ensure_ascii=False,indent=2))
    else:parser.error('PC supports --suite package|model')


if __name__=='__main__':main()
