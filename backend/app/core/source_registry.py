"""题目来源注册表：新增来源 = 新增一个 adapter 并注册到这里。"""
from .source_adapter import SourceAdapter, ThirdPartyAdapter


class TikuCnAdapter(ThirdPartyAdapter):
    name = "tiku.cn"

    def normalize(self, raw) -> list:
        # 占位 stub：tiku.cn 无公开 API，具体同步（爬虫/授权）后续实现。
        return []


SOURCE_REGISTRY: dict[str, SourceAdapter] = {
    "tiku.cn": TikuCnAdapter(),
}
