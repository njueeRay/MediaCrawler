"""
飞书同步配置管理
完全基于飞书官方Python SDK (lark-oapi) 规范
"""

import os
import logging

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv未安装，无法从.env文件加载配置")

class FeishuConfig:
    """飞书配置管理类 - 基于官方SDK规范"""
    
    # 飞书应用配置
    APP_ID = os.getenv("FEISHU_APP_ID", "")
    APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
    APP_TOKEN = os.getenv("FEISHU_APP_TOKEN", "")  # 多维表格的app_token
    TABLE_ID = os.getenv("FEISHU_TABLE_ID", "")   # 可选，不填会自动创建
    
    # 认证配置 - 官方SDK支持
    USER_ACCESS_TOKEN = os.getenv("FEISHU_USER_ACCESS_TOKEN", "")
    TENANT_ACCESS_TOKEN = os.getenv("FEISHU_TENANT_ACCESS_TOKEN", "")
    
    # 同步配置
    BATCH_SIZE = int(os.getenv("FEISHU_BATCH_SIZE", "500"))
    AUTO_SYNC = os.getenv("FEISHU_AUTO_SYNC", "true").lower() == "true"
    SYNC_INTERVAL = int(os.getenv("FEISHU_SYNC_INTERVAL", "300"))
    
    # 数据源配置
    DATA_DIR = os.getenv("DATA_DIR", "data/xhs/")
    JSON_FILE_PATTERN = os.getenv("JSON_FILE_PATTERN", "*.json")
    CSV_FILE_PATTERN = os.getenv("CSV_FILE_PATTERN", "*.csv")
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "feishu_sync.log")
    
    # API配置
    API_BASE_URL = os.getenv("FEISHU_API_BASE_URL", "https://open.feishu.cn/open-apis")
    REQUEST_TIMEOUT = int(os.getenv("FEISHU_REQUEST_TIMEOUT", "30"))
    RETRY_COUNT = int(os.getenv("FEISHU_RETRY_COUNT", "3"))
    RATE_LIMIT_DELAY = float(os.getenv("FEISHU_RATE_LIMIT_DELAY", "0.1"))
    
    # 数据处理配置
    MAX_TITLE_LENGTH = int(os.getenv("MAX_TITLE_LENGTH", "100"))
    MAX_DESC_LENGTH = int(os.getenv("MAX_DESC_LENGTH", "500"))
    MAX_TAGS_COUNT = int(os.getenv("MAX_TAGS_COUNT", "10"))
    
    @classmethod
    def validate(cls):
        """验证配置"""
        required_fields = ["APP_ID", "APP_SECRET", "APP_TOKEN"]
        missing_fields = [field for field in required_fields if not getattr(cls, field)]
        
        if missing_fields:
            raise ValueError(f"缺少必要配置: {missing_fields}")
        
        # 验证批量大小
        if cls.BATCH_SIZE <= 0 or cls.BATCH_SIZE > 500:
            logger.warning(f"批量大小 {cls.BATCH_SIZE} 超出范围，调整为500")
            cls.BATCH_SIZE = 500
        
        logger.info("配置验证通过")
        return True
    
    @classmethod
    def get_lark_client_config(cls):
        """获取官方SDK客户端配置"""
        try:
            import lark_oapi as lark
            
            # 根据官方SDK文档配置
            client = lark.Client.builder() \
                .app_id(cls.APP_ID) \
                .app_secret(cls.APP_SECRET) \
                .log_level(getattr(lark.LogLevel, cls.LOG_LEVEL, lark.LogLevel.INFO)) \
                .build()
            
            return client
        except ImportError:
            raise ImportError("lark-oapi未安装，请运行: pip install lark-oapi")
    
    @classmethod
    def get_request_option(cls):
        """获取请求选项 - 官方SDK格式"""
        try:
            import lark_oapi as lark
            
            # 构建请求选项
            option_builder = lark.RequestOption.builder()
            
            # 如果有用户访问令牌，使用用户令牌
            if cls.USER_ACCESS_TOKEN:
                option_builder.user_access_token(cls.USER_ACCESS_TOKEN)
            # 否则使用租户访问令牌（通常由app_id和app_secret自动获取）
            elif cls.TENANT_ACCESS_TOKEN:
                option_builder.tenant_access_token(cls.TENANT_ACCESS_TOKEN)
            
            return option_builder.build()
        except ImportError:
            raise ImportError("lark-oapi未安装，请运行: pip install lark-oapi")
    
    @classmethod
    def print_config_summary(cls):
        """打印配置摘要（隐藏敏感信息）"""
        logger.info("=== 飞书同步配置摘要 ===")
        logger.info(f"应用ID: {cls.APP_ID[:8]}..." if cls.APP_ID else "应用ID: 未配置")
        logger.info(f"应用密钥: {'已配置' if cls.APP_SECRET else '未配置'}")
        logger.info(f"表格Token: {cls.APP_TOKEN[:8]}..." if cls.APP_TOKEN else "表格Token: 未配置")
        logger.info(f"数据表ID: {cls.TABLE_ID if cls.TABLE_ID else '将自动创建'}")
        logger.info(f"批量大小: {cls.BATCH_SIZE}")
        logger.info(f"数据目录: {cls.DATA_DIR}")
        logger.info(f"自动同步: {'开启' if cls.AUTO_SYNC else '关闭'}")
        logger.info(f"同步间隔: {cls.SYNC_INTERVAL}秒")
        logger.info("=" * 30)

# 便捷访问函数
def get_config() -> FeishuConfig:
    """获取配置类"""
    return FeishuConfig

def validate_config() -> bool:
    """验证配置"""
    return FeishuConfig.validate()

def print_config():
    """打印配置摘要"""
    FeishuConfig.print_config_summary()
    # 飞书应用配置
    APP_ID = os.getenv("FEISHU_APP_ID", "")
    APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
    APP_TOKEN = os.getenv("FEISHU_APP_TOKEN", "")  # 多维表格的app_token
    TABLE_ID = os.getenv("FEISHU_TABLE_ID", "")   # 可选，不填会自动创建
    
    # 同步配置
    BATCH_SIZE = int(os.getenv("FEISHU_BATCH_SIZE", "500"))
    AUTO_SYNC = os.getenv("FEISHU_AUTO_SYNC", "true").lower() == "true"
    
    # 数据源配置
    DATA_DIR = os.getenv("DATA_DIR", "data/xhs/")
    JSON_FILE_PATTERN = os.getenv("JSON_FILE_PATTERN", "*.json")
    CSV_FILE_PATTERN = os.getenv("CSV_FILE_PATTERN", "*.csv")
    
    # API配置
    BASE_URL = "https://open.feishu.cn/open-apis"
    REQUEST_TIMEOUT = int(os.getenv("FEISHU_REQUEST_TIMEOUT", "30"))
    RETRY_TIMES = int(os.getenv("FEISHU_RETRY_TIMES", "3"))
    RATE_LIMIT_DELAY = float(os.getenv("FEISHU_RATE_LIMIT_DELAY", "0.1"))
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "feishu_sync.log")
    
    @classmethod
    def validate(cls):
        """验证配置"""
        required_fields = ["APP_ID", "APP_SECRET", "APP_TOKEN"]
        missing_fields = [field for field in required_fields if not getattr(cls, field)]
        
        if missing_fields:
            raise ValueError(f"缺少必要配置: {missing_fields}")
        
        return True
    
    @classmethod
    def get_config_dict(cls) -> dict:
        """获取配置字典"""
        return {
            "app_id": cls.APP_ID,
            "app_secret": cls.APP_SECRET,
            "app_token": cls.APP_TOKEN,
            "table_id": cls.TABLE_ID,
            "batch_size": cls.BATCH_SIZE,
            "auto_sync": cls.AUTO_SYNC,
            "data_dir": cls.DATA_DIR,
            "base_url": cls.BASE_URL,
            "request_timeout": cls.REQUEST_TIMEOUT,
            "retry_times": cls.RETRY_TIMES,
            "rate_limit_delay": cls.RATE_LIMIT_DELAY,
            "log_level": cls.LOG_LEVEL,
            "log_file": cls.LOG_FILE
        }
    
    @classmethod
    def print_config(cls):
        """打印配置信息（隐藏敏感信息）"""
        config = cls.get_config_dict()
        
        # 隐藏敏感信息
        sensitive_keys = ["app_secret"]
        for key in sensitive_keys:
            if config.get(key):
                config[key] = "*" * 8
        
        print("当前配置:")
        for key, value in config.items():
            print(f"  {key}: {value}")
