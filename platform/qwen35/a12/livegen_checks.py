"""Capture the PC policy/import checks and assertion-policy refusal command."""
import sys
import argparse
from livegen_evidence import ROOT,OUT,save
from livegen_build import run

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--revision',required=True,type=int);a=p.parse_args();assert a.tag.isalnum()
    run([sys.executable,ROOT/'platform/qwen35/a12/test_livegen_source.py','--tag',a.tag],'SOURCE_TEST_COMMAND-'+a.tag)
    run([sys.executable,ROOT/'platform/qwen35/a12/test_livegen_import.py','--tag',a.tag,'--revision',a.revision],'IMPORT_REVIEW_COMMAND-'+a.tag)
    # Under -O, refuse to run original assert-based gates, not silently waive them.
    command=[sys.executable,'-O','-c',"import sys;sys.path.insert(0,'/mnt/c/Patientqwen/platform/qwen35/a12');from livegen_platform import original_bo_validator;\ntry: original_bo_validator()\nexcept RuntimeError as e:\n assert_message=str(e);sys.exit(0 if 'unoptimized Python' in assert_message else 2)\nelse: sys.exit(3)"]
    run(command,'PYTHON_OPTIMIZE_REFUSAL-'+a.tag)
if __name__=='__main__':main()
