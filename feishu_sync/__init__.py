"""
飞书多维表格数据同步模块
完全基于飞书官方Python SDK (lark-oapi)

用于将MediaCrawler爬取的小红书数据同步到飞书多维表格
"""

__version__ = "1.0.0"
__author__ = "MediaCrawler Team"

import logging

logger = logging.getLogger(__name__)

# 检查官方SDK是否可用
try:
    import lark_oapi as lark
    SDK_AVAILABLE = True
    logger.info("飞书官方SDK可用")
except ImportError:
    SDK_AVAILABLE = False
    logger.error("飞书官方SDK未安装，请运行: pip install lark-oapi")

# 导出主要类和函数
try:
    from .config import FeishuConfig, get_config, validate_config, print_config
    from .data_formatter import XHSDataFormatter
    
    if SDK_AVAILABLE:
        from .sync_manager import FeishuSyncManager
        
        __all__ = [
            'FeishuConfig',
            'XHSDataFormatter', 
            'FeishuSyncManager',
            'get_config',
            'validate_config',
            'print_config'
        ]
    else:
        __all__ = [
            'FeishuConfig',
            'XHSDataFormatter',
            'get_config',
            'validate_config', 
            'print_config'
        ]
    
    logger.info(f"飞书同步包 v{__version__} 加载完成")
    
except ImportError as e:
    logger.error(f"包加载失败: {e}")
    __all__ = []

def get_version():
    """获取版本信息"""
    return __version__

def check_dependencies():
    """检查依赖包是否已安装"""
    dependencies = {
        'lark_oapi': 'lark-oapi',
        'pandas': 'pandas', 
        'dotenv': 'python-dotenv'
    }
    
    missing_deps = []
    
    for module, package in dependencies.items():
        try:
            __import__(module)
            logger.info(f"✅ {package} 已安装")
        except ImportError:
            missing_deps.append(package)
            logger.warning(f"❌ {package} 未安装")
    
    if missing_deps:
        logger.error(f"缺少依赖包: {', '.join(missing_deps)}")
        logger.error(f"请运行: pip install {' '.join(missing_deps)}")
        return False
    
    logger.info("所有依赖包已就绪")
    return True

def print_usage():
    """打印使用说明"""
    usage = """
飞书多维表格同步包使用说明：

1. 基本用法：
   from feishu_sync import FeishuSyncManager, FeishuConfig
   
   config = FeishuConfig()
   manager = FeishuSyncManager()
   result = manager.sync_from_csv("data.csv")

2. 配置管理：
   from feishu_sync import get_config, validate_config
   
   config = get_config()
   if validate_config():
       print("配置有效")

3. 命令行工具：
   python sync_to_feishu.py --help

更多信息请参考: docs/feishu/飞书开发说明.md
   """
    print(usage)

if __name__ == "__main__":
    print_usage()
    check_dependencies()
