import threading
import time

from client.buffer import BufferManager, BufferedSegment


def seg(segment_id: int, duration: float = 2.0) -> BufferedSegment:
    return BufferedSegment(
        segment_id=segment_id, representation="720p",
        bitrate=2_500_000, duration=duration, size=1000,
    )


def test_fifo_order():
    buf = BufferManager(max_seconds=60)
    for i in range(1, 4):
        buf.put(seg(i))
    order = [buf.get().segment_id for _ in range(3)]
    assert order == [1, 2, 3]


def test_buffer_level_tracks_duration():
    buf = BufferManager(max_seconds=60)
    buf.put(seg(1, duration=2.0))
    buf.put(seg(2, duration=3.0))
    assert buf.level == 5.0
    buf.get()
    assert buf.level == 3.0
    assert buf.size == 1


def test_get_empty_returns_none():
    assert BufferManager().get(timeout=0.01) is None


def test_buffer_full_blocks_until_consumed():
    buf = BufferManager(max_seconds=4.0)
    buf.put(seg(1, 2.0))
    buf.put(seg(2, 2.0))

    done = threading.Event()

    def producer():
        buf.put(seg(3, 2.0), timeout=5.0)  # must block until a slot frees
        done.set()

    t = threading.Thread(target=producer)
    t.start()
    time.sleep(0.1)
    assert not done.is_set(), "put should block while buffer is full"
    buf.get()
    t.join(timeout=2.0)
    assert done.is_set()
    assert buf.level == 4.0
