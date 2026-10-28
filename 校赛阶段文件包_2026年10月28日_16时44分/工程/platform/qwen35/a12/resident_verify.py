"""Audit explicitly named recorded PC windows; never execute model or Board."""
import argparse
from resident_evidence import OUT, read, save
from resident_audit import audit


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('windows',nargs='+');a=p.parse_args()
    results=[]
    for tag in a.windows:
        result=audit(tag)
        dest=OUT/tag/'AUDIT.json'
        if dest.exists():
            if read(dest)!=result:raise RuntimeError('existing audit differs; preserve and use a new named review')
        else:save(dest,result)
        results.append(result);print(result['status'],tag,flush=True)
    save(OUT/(a.tag+'.json'),dict(status='PASS_EXPLICIT_RAW_PC_WINDOWS',windows=results,BOARD='NOT_TESTED',release_allowed=False))


if __name__=='__main__':main()
