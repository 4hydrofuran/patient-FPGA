"""Use the exact archived-lease and complete-scan audit with task10 evidence paths."""
import sys
from common import ROOT
if __name__=='__main__':
    source=(ROOT/'platform/qwen35/a12/step09_lifecycle_supplement.py').read_text(encoding='utf-8')
    source=source.replace('from step09_common import OUT','from step10_common import OUT')
    source=source.replace("choices=['short','context']","choices=['baseline','optimized']")
    exec(compile(source,'task10_exact_lifecycle_audit','exec'),{'__name__':'__main__'})
