#!/bin/bash

# MediaCrawler-飞书同步平台 - 快速设置脚本
# 自动安装依赖、配置环境、初始化服务

set -e

echo "🚀 MediaCrawler-飞书同步平台 初始化"
echo "========================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查Python版本
check_python() {
    log_info "检查Python版本..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        log_success "Python版本: $PYTHON_VERSION"
    else
        log_error "Python3未安装，请先安装Python 3.8+"
        exit 1
    fi
}

# 安装Python依赖
install_dependencies() {
    log_info "安装Python依赖包..."
    
    # 检查是否有虚拟环境
    if [[ ! -d "venv" ]]; then
        log_info "创建虚拟环境..."
        python3 -m venv venv
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    # 安装基础依赖
    log_info "安装核心依赖..."
    pip install requests python-dotenv pandas schedule watchdog
    
    # 安装AI相关依赖（可选）
    read -p "是否安装AI数据清洗功能? (y/n): " install_ai
    if [[ $install_ai == "y" || $install_ai == "Y" ]]; then
        log_info "安装AI依赖..."
        pip install openai tiktoken
    fi
    
    # 安装监控依赖（可选）
    read -p "是否安装监控功能? (y/n): " install_monitoring
    if [[ $install_monitoring == "y" || $install_monitoring == "Y" ]]; then
        log_info "安装监控依赖..."
        pip install psutil prometheus-client
    fi
    
    log_success "依赖安装完成"
}

# 配置环境变量
setup_environment() {
    log_info "配置飞书应用信息..."
    
    if [[ ! -f ".env" ]]; then
        echo "请输入飞书应用配置信息:"
        read -p "APP_ID: " app_id
        read -p "APP_SECRET: " app_secret
        read -p "APP_TOKEN: " app_token
        
        cat > .env << EOF
# 飞书应用配置
FEISHU_APP_ID=$app_id
FEISHU_APP_SECRET=$app_secret
FEISHU_APP_TOKEN=$app_token

# 数据处理配置
BATCH_SIZE=50
RETRY_TIMES=3
LOG_LEVEL=INFO

# AI配置（可选）
# OPENAI_API_KEY=your_openai_key
# AI_MODEL=gpt-3.5-turbo
# QUALITY_THRESHOLD=0.7

# 监控配置
METRICS_ENABLED=true
ALERT_ENABLED=false
EOF
        
        log_success "环境配置已保存到 .env"
    else
        log_warning ".env 文件已存在，跳过配置"
    fi
}

# 创建必要目录
create_directories() {
    log_info "创建目录结构..."
    
    # 数据目录
    mkdir -p data/xhs/json
    mkdir -p data/backup
    
    # 日志目录
    mkdir -p logs
    
    # 配置目录
    mkdir -p config
    
    log_success "目录结构创建完成"
}

# 测试连接
test_connection() {
    log_info "测试飞书API连接..."
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 运行连接测试
    python3 -c "
from feishu_sync.config import load_config_from_env
from feishu_sync_simple import FeishuSimpleSync

try:
    config = load_config_from_env()
    sync = FeishuSimpleSync(
        app_id=config['app_id'],
        app_secret=config['app_secret'],
        app_token=config['app_token']
    )
    
    token = sync.get_access_token()
    if token:
        print('✅ 飞书API连接成功')
    else:
        print('❌ 飞书API连接失败')
        exit(1)
        
except Exception as e:
    print(f'❌ 连接测试失败: {e}')
    exit(1)
"
    
    if [[ $? -eq 0 ]]; then
        log_success "飞书API连接测试通过"
    else
        log_error "飞书API连接测试失败，请检查配置"
        exit 1
    fi
}

# 创建示例配置
create_sample_configs() {
    log_info "创建示例配置文件..."
    
    # 工作流配置示例
    cat > config/workflow_example.yaml << 'EOF'
# 工作流配置示例
name: "daily_xiaohongshu_sync"
description: "每日小红书数据同步"
schedule: "0 2 * * *"  # 每日2点执行

tasks:
  - name: "check_new_data"
    type: "file_check"
    config:
      directory: "data/xhs/json"
      pattern: "*.json"
      max_age_hours: 24
      
  - name: "ai_data_clean"
    type: "ai_processor"
    depends_on: ["check_new_data"]
    config:
      quality_threshold: 0.7
      remove_spam: true
      generate_summary: false
      
  - name: "sync_to_feishu"
    type: "feishu_sync"
    depends_on: ["ai_data_clean"]
    config:
      batch_size: 50
      retry_times: 3
      create_backup: true

alerts:
  - name: "sync_failure"
    condition: "task_failed"
    actions: ["log", "email"]
    
  - name: "data_quality_low"
    condition: "quality_score < 0.5"
    actions: ["log", "slack"]
EOF

    # 启动脚本
    cat > start_scheduler.sh << 'EOF'
#!/bin/bash
# 启动自动化调度器

echo "🚀 启动MediaCrawler自动化调度器"

# 激活虚拟环境
source venv/bin/activate

# 启动调度器
python3 auto_scheduler.py --mode daemon

echo "👋 调度器已停止"
EOF

    chmod +x start_scheduler.sh
    
    # 停止脚本
    cat > stop_scheduler.sh << 'EOF'
#!/bin/bash
# 停止自动化调度器

echo "🛑 停止MediaCrawler自动化调度器"

# 查找并终止调度器进程
pkill -f "auto_scheduler.py"

echo "✅ 调度器已停止"
EOF

    chmod +x stop_scheduler.sh
    
    log_success "示例配置文件已创建"
}

# 显示使用说明
show_usage() {
    cat << 'EOF'

🎉 MediaCrawler-飞书同步平台 安装完成！

📖 使用说明:

1. 手动同步单个文件:
   source venv/bin/activate
   python3 feishu_sync_simple.py --file data/xhs/json/your_file.json

2. 批量同步目录:
   python3 feishu_sync_simple.py --dir data/xhs/json/

3. 启动自动化调度器:
   ./start_scheduler.sh

4. 停止自动化调度器:
   ./stop_scheduler.sh

5. 单次执行特定任务:
   python3 auto_scheduler.py --mode once --task daily

📁 目录结构:
├── data/xhs/json/          # 爬虫数据目录
├── logs/                   # 日志目录
├── config/                 # 配置目录
├── venv/                   # Python虚拟环境
├── .env                    # 环境变量配置
└── *.py                    # 核心程序文件

🔗 相关链接:
- 项目文档: docs/feishu/
- 飞书开放平台: https://open.feishu.cn/
- 问题反馈: https://github.com/njueeRay/MediaCrawler/issues

EOF
}

# 主函数
main() {
    check_python
    install_dependencies
    setup_environment
    create_directories
    test_connection
    create_sample_configs
    show_usage
    
    log_success "🎉 安装完成! 请阅读上方使用说明开始使用"
}

# 错误处理
trap 'log_error "安装过程中出现错误，请检查上方日志"; exit 1' ERR

# 执行主函数
main "$@"
