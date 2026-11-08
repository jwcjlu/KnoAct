"""题目来源注册表：新增第三方来源 = 新增一个 adapter 并注册到这里。

manual / photo 来源由 ManualAdapter / OcrAdapter 在调用点直接使用，不在此注册；
本注册表只收录第三方题库 adapter（当前仅 tiku.cn 占位）。
"""
from .source_adapter import SourceAdapter, ThirdPartyAdapter


class TikuCnAdapter(ThirdPartyAdapter):
    name = "tiku.cn"

    def normalize(self, raw) -> list:
        # 占位 stub：tiku.cn 无公开 API，具体同步（爬虫/授权）后续实现。
        return []


SOURCE_REGISTRY: dict[str, SourceAdapter] = {
    "tiku.cn": TikuCnAdapter(),
}
