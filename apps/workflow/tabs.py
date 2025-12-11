# 文件路径: apps/workflow/tabs.py
# (这是一个新文件)

from django.http import HttpRequest

# 1. 从你的两个 admin 文件中导入各自的 Tab 生成器
from .creative.admin import get_creative_project_tabs
from .inference.admin import get_inference_project_tabs


def get_global_tabs(request: HttpRequest) -> list[dict]:
    """
    (新) 这是一个中央回调函数，在 settings.py 中被 UNFOLD["TABS"] 引用。

    它负责收集所有子包的 Tab 配置，并将它们组合成一个
    Unfold 期望的单一列表。
    """

    # 2. 调用两个函数
    inference_tabs = get_inference_project_tabs(request)
    creative_tabs = get_creative_project_tabs(request)
    # 3. 返回组合后的列表
    # (Unfold 将收到: [{"models": ...}, {"models": ...}])
    return inference_tabs + creative_tabs
