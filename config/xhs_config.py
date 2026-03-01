# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/config/xhs_config.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。


# 小红书平台配置

# 排序方式，具体的枚举值在media_platform/xhs/field.py中
SORT_TYPE = "popularity_descending"

# 时间范围筛选（发布时间）
# 优先读取环境变量（由 WebUI crawler_manager 注入）
import os as _os
_XHS_DATE_START: str = _os.environ.get("XHS_DATE_START", "")
_XHS_DATE_END: str = _os.environ.get("XHS_DATE_END", "")
XHS_ENABLE_TIME_RANGE: bool = bool(_XHS_DATE_START)
START_DAY: str = _XHS_DATE_START or "2026-01-01"
END_DAY: str = _XHS_DATE_END or "2026-01-20"

# 指定笔记URL列表, 必须要携带xsec_token参数
XHS_SPECIFIED_NOTE_URL_LIST = [
    # "https://www.xiaohongshu.com/explore/64b95d01000000000c034587?xsec_token=AB0EFqJvINCkj6xOCKCQgfNNh8GdnBC_6XecG4QOddo3Q=&xsec_source=pc_cfeed"
    # ........................
]

# 指定创作者URL列表，需要携带xsec_token和xsec_source参数

XHS_CREATOR_ID_LIST = [
    # "https://www.xiaohongshu.com/user/profile/5f58bd990000000001003753?xsec_token=ABYVg1evluJZZzpMX-VWzchxQ1qSNVW3r-jOEnKqMcgZw=&xsec_source=pc_search",
    # ........................
    # 杭州AI工坊
    "https://www.xiaohongshu.com/user/profile/5cc5d87400000000120278a2?xsec_token=ABvhaIB3BS-FoO-wjnxlFjmaxXnQmfM17HGHt4B1TT0QU%3D&xsec_source=pc_search"
]
