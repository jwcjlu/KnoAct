import asyncio
from app.core.stream import StreamEvent, StreamBus


def test_stream_bus_subscribe_receives_events():
    bus = StreamBus()
    q = bus.subscribe()
    bus.emit(StreamEvent(type="tool_call", data={"tool": "lookup_word"}))
    bus.emit(StreamEvent(type="final", data={"answer": "好"}))
    assert len(bus.events) == 2
    assert q.qsize() == 2
    e1 = asyncio.run(q.get())
    assert e1.type == "tool_call"
    e2 = asyncio.run(q.get())
    assert e2.type == "final"


def test_stream_bus_no_queue_without_subscribe():
    bus = StreamBus()
    bus.emit(StreamEvent(type="final", data={"answer": "好"}))
    assert bus._queue is None
    assert len(bus.events) == 1
