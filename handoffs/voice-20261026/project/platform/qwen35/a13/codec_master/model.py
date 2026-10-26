"""固定I2S合同的独立帧语义模型；先于RTL建立。"""
import random
import unittest


def bits(word):
    return [(word >> index) & 1 for index in range(15, -1, -1)]


def slots(frames):
    """输出下降沿后的LR/ADC值；边界拍发送前一字LSB。"""
    previous_right = 0
    for frame in frames:
        left, right = bits(frame & 65535), bits(frame >> 16)
        yield from [(0, previous_right)] + [(0, b) for b in left[:15]]
        yield from [(1, left[15])] + [(1, b) for b in right[:15]]
        previous_right = right[15]
    yield 0, previous_right


def decode(stream):
    """上升沿数据语义：先收最后一位，再响应LR变化。"""
    channel = 1
    locked = False
    word = 0
    count = 0
    left = 0
    result = []
    for lr, bit in stream:
        if locked:
            word = ((word << 1) | bit) & 65535
        if lr != channel:
            if locked:
                if count != 15:
                    raise ValueError('not a 16-bit I2S slot')
                if channel == 0:
                    left = word
                else:
                    result.append(left | (word << 16))
            if lr == 0:
                locked = True
            channel, count, word = lr, 0, 0
        elif locked:
            count += 1
            if count > 15:
                raise ValueError('missing LR boundary')
    return result


class ElasticFrame:
    """单帧弹性缓存：只在valid且ready时移交；设备消耗独立建模。"""
    def __init__(self):
        self.pending = None
        self.fault = False

    def push(self, value):
        if self.pending is not None:
            self.fault = True
            return False
        self.pending = value
        return True

    def take(self):
        value, self.pending = self.pending, None
        if value is None:
            self.fault = True
        return value

    def stop(self):
        self.pending = None
        self.fault = False


class TestContract(unittest.TestCase):
    def test_roundtrip(self):
        rng = random.Random(8960)
        frames = [0, 0xffffffff, 0x80017fff, 0x00018000] + [rng.getrandbits(32) for _ in range(2048)]
        self.assertEqual(decode(slots(frames)), frames)

    def test_boundary_lsb(self):
        self.assertEqual(decode(slots([0x00010001, 0x80018001])), [0x00010001, 0x80018001])

    def test_wrong_slot(self):
        malformed = list(slots([0xabcdef01]))
        del malformed[5]
        with self.assertRaises(ValueError):
            decode(malformed)

    def test_backpressure(self):
        queue = ElasticFrame()
        self.assertTrue(queue.push(0x12345678))
        self.assertFalse(queue.push(0xabcd))
        self.assertEqual(queue.take(), 0x12345678)
        self.assertTrue(queue.fault)

    def test_underrun_restart(self):
        queue = ElasticFrame()
        self.assertIsNone(queue.take())
        self.assertTrue(queue.fault)
        queue.push(12)
        queue.stop()
        self.assertIsNone(queue.pending)
        self.assertFalse(queue.fault)


if __name__ == '__main__':
    unittest.main(verbosity=2)
