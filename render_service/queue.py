"""进程内任务队列 + 有限并发。"""
import threading
from collections import deque
from typing import Any, Callable


class TaskQueue:
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._lock = threading.Lock()
        self._queue: deque[tuple[str, Callable, Callable | None]] = deque()
        self.status: dict[str, dict[str, Any]] = {}

    def submit(self, task_id: str, job: Callable, status_cb: Callable[[str], None] | None = None):
        """job(task_id, status_cb) -> video_url。入队。"""
        with self._lock:
            self.status[task_id] = {"status": "queued", "video_url": None, "error": None, "progress": 0}
            self._queue.append((task_id, job, status_cb))

    def drain(self):
        """同步跑完队列里所有任务（测试/简化用）。"""
        while True:
            with self._lock:
                if not self._queue:
                    break
                tid, job, cb = self._queue.popleft()
            self._run_one(tid, job, cb)

    def _run_one(self, tid, job, cb):
        def on_status(s):
            with self._lock:
                self.status[tid]["status"] = s
            if cb:
                cb(s)
        try:
            url = job(tid, on_status)
            with self._lock:
                self.status[tid]["status"] = "done"
                self.status[tid]["video_url"] = url
        except Exception as e:
            with self._lock:
                self.status[tid]["status"] = "error"
                self.status[tid]["error"] = str(e)
