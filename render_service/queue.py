"""进程内任务队列 + 有限并发（线程模型）。"""
import threading
from typing import Any, Callable


class TaskQueue:
    def __init__(self, max_concurrent: int = 3):
        self._sem = threading.Semaphore(max_concurrent)
        self._lock = threading.Lock()
        self.status: dict[str, dict[str, Any]] = {}
        self._threads: list[threading.Thread] = []
        self._active = 0
        self._cond = threading.Condition()

    def submit(self, task_id: str, job: Callable, status_cb: Callable[[str], None] | None = None):
        with self._lock:
            self.status[task_id] = {"status": "queued", "video_url": None, "error": None, "progress": 0}
            self._active += 1
        t = threading.Thread(target=self._worker, args=(task_id, job, status_cb), daemon=True)
        self._threads.append(t)
        t.start()

    def _worker(self, task_id, job, status_cb):
        with self._sem:
            self._set_status(task_id, "generating")
            def on_status(s):
                self._set_status(task_id, s)
                if status_cb:
                    status_cb(s)
            try:
                url = job(task_id, on_status)
                with self._lock:
                    self.status[task_id]["status"] = "done"
                    self.status[task_id]["video_url"] = url
            except Exception as e:
                with self._lock:
                    self.status[task_id]["status"] = "error"
                    self.status[task_id]["error"] = str(e)
            finally:
                with self._cond:
                    self._active -= 1
                    self._cond.notify_all()

    def _set_status(self, task_id, s):
        with self._lock:
            self.status[task_id]["status"] = s

    def drain(self):
        """等待所有已提交的任务跑完（同步/测试用）。"""
        with self._cond:
            while self._active > 0:
                self._cond.wait()
