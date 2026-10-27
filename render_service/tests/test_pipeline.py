# render_service/tests/test_pipeline.py
from render_service.queue import TaskQueue


def test_queue_reports_status():
    q = TaskQueue(max_concurrent=1)
    states = {}
    tid = "t1"

    def fake_job(tid, status_cb):
        status_cb("rendering")
        status_cb("done")
        return "http://x/final.mp4"

    q.submit(tid, fake_job, status_cb=lambda s: states.setdefault(tid, []).append(s))
    q.drain()  # 同步跑完队列里的任务
    assert states["t1"] == ["rendering", "done"]
    assert q.status["t1"]["status"] == "done"
    assert q.status["t1"]["video_url"] == "http://x/final.mp4"
