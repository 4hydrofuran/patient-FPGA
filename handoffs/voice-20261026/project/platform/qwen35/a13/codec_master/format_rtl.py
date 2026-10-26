"""调用只读技能内置formatter，保存原稿并验证格式化收敛。"""
import argparse
from pathlib import Path
import shutil
import sys

SKILL = Path('C:/Users/Fang/.codex/skills/verilog-generator')
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))
from scripts.python.quality.formatter_config import create_formatter_backend


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('attempt')
    args = parser.parse_args()
    backup = ROOT.parents[3] / 'evidence/a13_A/20261025-audio-codec-master-v1' / args.attempt
    backup.mkdir(exist_ok=False)
    for path in sorted((ROOT / 'rtl').glob('*.v')):
        shutil.copyfile(path, backup / path.name)
        backend = create_formatter_backend()
        original = path.read_text(encoding='utf-8')
        formatted = backend.format_text(original, path)
        # 首轮生成器分组重排失败已保留；只接收最终一次检查字节不变的候选。
        for _ in range(4):
            candidate = backend.format_text(formatted, path)
            if candidate == formatted:
                break
            formatted = candidate
        assert backend.format_text(formatted, path) == formatted, path
        path.write_text(formatted, encoding='utf-8', newline='\n')
        print(path.name, 'FORMAT_CONVERGED_NOT_FUNCTIONAL_PROOF')


if __name__ == '__main__':
    main()
