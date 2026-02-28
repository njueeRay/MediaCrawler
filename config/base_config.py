# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/config/base_config.py
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

# 基础配置
import os

def _env(key: str, default, type_fn=str):
    """从环境变量读取配置，支持 str/int/float/bool 类型转换。
    配合 config/__init__.py 中的 load_dotenv()，实现 .env → os.environ → config 变量。
    """
    val = os.getenv(key)
    if val is None:
        return default
    if type_fn is bool:
        return val.strip().lower() in ("true", "1", "yes", "on")
    try:
        return type_fn(val)
    except (ValueError, TypeError):
        return default


PLATFORM = _env("PLATFORM", "xhs")  # 平台，xhs | dy | ks | bili | wb | tieba | zhihu | wechat
KEYWORDS = _env("KEYWORDS", "Python学习")  # 关键词搜索配置，以英文逗号分隔
LOGIN_TYPE = _env("LOGIN_TYPE", "qrcode")  # qrcode or phone or cookie
COOKIES = _env("COOKIES", "")
CRAWLER_TYPE = _env("CRAWLER_TYPE", "search")  # search | detail | creator
# 是否开启 IP 代理
ENABLE_IP_PROXY = _env("ENABLE_IP_PROXY", False, bool)

# 代理IP池数量
IP_PROXY_POOL_COUNT = _env("IP_PROXY_POOL_COUNT", 2, int)

# 代理IP提供商名称
IP_PROXY_PROVIDER_NAME = _env("IP_PROXY_PROVIDER_NAME", "kuaidaili")  # kuaidaili | wandouhttp

# 设置为True不会打开浏览器（无头浏览器）
# 设置False会打开一个浏览器
# 小红书如果一直扫码登录不通过，打开浏览器手动过一下滑动验证码
# 抖音如果一直提示失败，打开浏览器看下是否扫码登录之后出现了手机号验证，如果出现了手动过一下再试。
HEADLESS = _env("HEADLESS", False, bool)

# 是否保存登录状态
SAVE_LOGIN_STATE = _env("SAVE_LOGIN_STATE", True, bool)

# ==================== CDP (Chrome DevTools Protocol) 配置 ====================
# 是否启用CDP模式 - 使用用户现有的Chrome/Edge浏览器进行爬取，提供更好的反检测能力
# 启用后将自动检测并启动用户的Chrome/Edge浏览器，通过CDP协议进行控制
# 这种方式使用真实的浏览器环境，包括用户的扩展、Cookie和设置，大大降低被检测的风险
ENABLE_CDP_MODE = _env("ENABLE_CDP_MODE", True, bool)

# CDP调试端口
CDP_DEBUG_PORT = _env("CDP_DEBUG_PORT", 9222, int)

# 自定义浏览器路径（可选，为空则自动检测）
CUSTOM_BROWSER_PATH = _env("CUSTOM_BROWSER_PATH", "")

# CDP模式下是否启用无头模式
CDP_HEADLESS = _env("CDP_HEADLESS", False, bool)

# 浏览器启动超时时间（秒）
BROWSER_LAUNCH_TIMEOUT = _env("BROWSER_LAUNCH_TIMEOUT", 60, int)

# 是否在程序结束时自动关闭浏览器
AUTO_CLOSE_BROWSER = _env("AUTO_CLOSE_BROWSER", True, bool)

# 数据保存类型选项配置,支持六种类型：csv、db、json、sqlite、excel、postgres, 最好保存到DB，有排重的功能。
# WebUI 场景下推荐 sqlite（任务历史/订阅管理均依赖 DB session），如不配置 .env 则以此为默认值。
SAVE_DATA_OPTION = _env("SAVE_DATA_OPTION", "sqlite")  # csv or db or json or sqlite or excel or postgres

# 用户浏览器缓存的浏览器文件配置
USER_DATA_DIR = _env("USER_DATA_DIR", "%s_user_data_dir")  # %s will be replaced by platform name

# 爬取开始页数 默认从第一页开始
START_PAGE = _env("START_PAGE", 1, int)

# 爬取视频/帖子的数量控制
CRAWLER_MAX_NOTES_COUNT = _env("CRAWLER_MAX_NOTES_COUNT", 100, int)

# 并发爬虫数量控制
MAX_CONCURRENCY_NUM = _env("MAX_CONCURRENCY_NUM", 1, int)

# 是否开启爬媒体模式（包含图片或视频资源），默认不开启爬媒体
ENABLE_GET_MEIDAS = _env("ENABLE_GET_MEIDAS", True, bool)

# 是否开启爬评论模式, 默认开启爬评论
ENABLE_GET_COMMENTS = _env("ENABLE_GET_COMMENTS", False, bool)

# 爬取一级评论的数量控制(单视频/帖子)
CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = _env("CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES", 10, int)

# 是否开启爬二级评论模式, 默认不开启爬二级评论
ENABLE_GET_SUB_COMMENTS = _env("ENABLE_GET_SUB_COMMENTS", False, bool)

# 词云相关
ENABLE_GET_WORDCLOUD = _env("ENABLE_GET_WORDCLOUD", False, bool)

# 自定义词语及其分组
CUSTOM_WORDS = {
    "零几": "年份",
    "高频词": "专业术语",
}

# 停用(禁用)词文件路径
STOP_WORDS_FILE = _env("STOP_WORDS_FILE", "./docs/hit_stopwords.txt")

# 中文字体文件路径
FONT_PATH = _env("FONT_PATH", "./docs/STZHONGS.TTF")

# 爬取间隔时间
CRAWLER_MAX_SLEEP_SEC = _env("CRAWLER_MAX_SLEEP_SEC", 2, int)

# 平台 Cookie（可通过 WebUI 配置）
XHS_COOKIES = _env("XHS_COOKIES", "")
DY_COOKIES = _env("DY_COOKIES", "")
BILI_COOKIES = _env("BILI_COOKIES", "")
WB_COOKIES = _env("WB_COOKIES", "")
KS_COOKIES = _env("KS_COOKIES", "")
TIEBA_COOKIES = _env("TIEBA_COOKIES", "")
ZHIHU_COOKIES = _env("ZHIHU_COOKIES", "")

from .bilibili_config import *
from .xhs_config import *
from .dy_config import *
from .ks_config import *
from .weibo_config import *
from .tieba_config import *
from .zhihu_config import *
from .wechat_config import *
from .feishu_config import *
