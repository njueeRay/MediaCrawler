# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/config/__init__.py
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

try:
	from dotenv import load_dotenv

	load_dotenv()
except ImportError:
	# python-dotenv is optional; fall back to OS env only
	pass

from .base_config import *
from .db_config import *


def reload_from_env():
    """重新从 .env 和 os.environ 加载配置到 config 模块。
    WebUI 修改 .env 后调用此函数使改动立即生效。
    """
    import importlib
    import config as _config_mod

    # 1. 重新加载 .env 到 os.environ (override=True 覆盖已有值)
    try:
        from dotenv import load_dotenv as _ld
        _ld(override=True)
    except ImportError:
        pass

    # 2. 重新加载 base_config (会重新执行 _env() 读取 os.environ)
    from config import base_config as _base
    importlib.reload(_base)

    # 3. 重新加载 db_config (已经使用 os.getenv)
    from config import db_config as _db
    importlib.reload(_db)

    # 4. 同步到 config 模块命名空间
    for name in dir(_base):
        if not name.startswith('_'):
            setattr(_config_mod, name, getattr(_base, name))
    for name in dir(_db):
        if not name.startswith('_'):
            setattr(_config_mod, name, getattr(_db, name))
