"""题目来源注册表：新增第三方来源 = 新增一个 adapter 并注册到这里。

manual / photo 来源由 ManualAdapter / OcrAdapter 在调用点直接使用，不在此注册；
本注册表收录第三方题库 adapter（tiku.cn、学库宝 xuekubao 等）。
"""
from .source_adapter import SourceAdapter
from .tiku_cn_adapter import TikuCnAdapter
from .xuekubao_adapter import XuekubaoAdapter

SOURCE_REGISTRY: dict[str, SourceAdapter] = {
    "tiku.cn": TikuCnAdapter(),
    "xuekubao": XuekubaoAdapter(),
}
