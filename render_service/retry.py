"""渲染失败纠错：把错误喂回生成器重试，最多 max_retries 次。"""


def render_with_retry(initial_code, gen_fn, render_fn, out_dir, max_retries=3) -> str | None:
    """gen_fn(prev_error) -> new_code；render_fn(code, out_dir) -> mp4|None。

    循环：渲染 → 失败则 gen_fn(错误) 重新生成 → 再渲染，直到成功或次数耗尽。
    """
    code = initial_code
    for _ in range(max_retries + 1):
        mp4 = render_fn(code, out_dir)
        if mp4:
            return mp4
        # 失败：把「错误」交给生成器（这里简化传代码；真实 stderr 在 Task 10 接）
        code = gen_fn("previous render failed")
    return None
