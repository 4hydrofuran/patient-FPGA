"""用独立帧模型生成仿真输入，不依赖RTL内部节点作为判定基准。"""
import json
from pathlib import Path
import random
from model import decode, slots


def main():
    rng = random.Random(8960)
    frames = [0x00010001, 0xffff0000, 0x80017fff, 0x7fff8001]
    frames += [rng.getrandbits(32) for _ in range(1020)]
    assert decode(slots(frames)) == frames
    path = Path.cwd() / 'frames.hex'
    with path.open('x') as stream:
        stream.writelines(f'{word:08x}\n' for word in frames)
    print(json.dumps({'frames': len(frames), 'independent_model_roundtrip': True}))


if __name__ == '__main__':
    main()
