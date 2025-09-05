#!/usr/bin/env python3
"""
飞书同步功能验证脚本
用于测试各个组件是否正常工作
"""

import os
import sys
import logging

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_imports():
    """测试模块导入"""
    print("🔍 测试模块导入...")
    
    try:
        from feishu_sync.config import FeishuConfig
        print("✅ FeishuConfig 导入成功")
    except ImportError as e:
        print(f"❌ FeishuConfig 导入失败: {e}")
        return False
    
    try:
        from feishu_sync.data_formatter import XHSDataFormatter
        print("✅ XHSDataFormatter 导入成功")
    except ImportError as e:
        print(f"❌ XHSDataFormatter 导入失败: {e}")
        return False
    
    try:
        from feishu_sync.sync_manager import FeishuSyncManager
        print("✅ FeishuSyncManager 导入成功")
    except ImportError as e:
        print(f"❌ FeishuSyncManager 导入失败: {e}")
        return False
    
    return True

def test_dependencies():
    """测试依赖包"""
    print("\\n📦 测试依赖包...")
    
    dependencies = [
        ('lark_oapi', 'lark-oapi'),
        ('pandas', 'pandas'),
        ('dotenv', 'python-dotenv'),
        ('schedule', 'schedule')
    ]
    
    missing_deps = []
    
    for module, package in dependencies:
        try:
            __import__(module)
            print(f"✅ {package} 已安装")
        except ImportError:
            print(f"❌ {package} 未安装")
            missing_deps.append(package)
    
    if missing_deps:
        print(f"\\n⚠️  缺少依赖包: {', '.join(missing_deps)}")
        print(f"请运行: pip install {' '.join(missing_deps)}")
        return False
    
    return True

def test_config():
    """测试配置"""
    print("\\n⚙️  测试配置...")
    
    try:
        from feishu_sync.config import FeishuConfig
        config = FeishuConfig()
        
        # 检查关键配置
        required_configs = ['APP_ID', 'APP_SECRET', 'APP_TOKEN']
        missing_configs = []
        
        for cfg in required_configs:
            if not getattr(config, cfg, None):
                missing_configs.append(cfg)
        
        if missing_configs:
            print(f"❌ 缺少配置: {missing_configs}")
            print("请创建 .env 文件并配置必要信息")
            print("运行 'python sync_to_feishu.py --create-env' 创建配置模板")
            return False
        else:
            print("✅ 配置检查通过")
            return True
            
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False

def test_data_formatter():
    """测试数据格式化器"""
    print("\\n🔄 测试数据格式化器...")
    
    try:
        from feishu_sync.data_formatter import XHSDataFormatter
        formatter = XHSDataFormatter()
        
        # 测试数据
        test_data = {
            "note_id": "test_123",
            "title": "测试标题",
            "desc": "测试描述内容",
            "type": "normal",
            "time": "1693900800000",
            "user_id": "user_123",
            "nickname": "测试用户",
            "liked_count": "100",
            "collected_count": "50",
            "comment_count": "20",
            "share_count": "10",
            "ip_location": "北京",
            "tag_list": "标签1,标签2",
            "source_keyword": "测试关键词",
            "note_url": "https://example.com",
            "last_modify_ts": "1693900900000"
        }
        
        # 格式化测试
        result = formatter.format_single_record(test_data)
        
        if result and "fields" in result:
            print("✅ 数据格式化测试通过")
            print(f"   格式化字段数: {len(result['fields'])}")
            return True
        else:
            print("❌ 数据格式化测试失败")
            return False
            
    except Exception as e:
        print(f"❌ 数据格式化器测试失败: {e}")
        return False

def test_csv_loading():
    """测试CSV文件加载"""
    print("\\n📄 测试CSV文件加载...")
    
    # 检查是否有CSV文件
    csv_files = []
    data_dir = "data/xhs/"
    
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith('.csv'):
                csv_files.append(os.path.join(data_dir, file))
    
    if not csv_files:
        print("⚠️  未找到CSV文件进行测试")
        return True
    
    try:
        from feishu_sync.data_formatter import XHSDataFormatter
        formatter = XHSDataFormatter()
        
        # 测试第一个CSV文件
        test_file = csv_files[0]
        print(f"   测试文件: {test_file}")
        
        data = formatter.load_from_csv(test_file)
        
        if data:
            print(f"✅ CSV加载成功，数据条数: {len(data)}")
            return True
        else:
            print("❌ CSV加载失败")
            return False
            
    except Exception as e:
        print(f"❌ CSV文件加载测试失败: {e}")
        return False

def test_main_script():
    """测试主脚本"""
    print("\\n🚀 测试主脚本...")
    
    try:
        # 测试帮助信息
        import subprocess
        result = subprocess.run([
            sys.executable, "sync_to_feishu.py", "--help"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ 主脚本可以正常运行")
            return True
        else:
            print(f"❌ 主脚本运行失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 主脚本测试失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("🔍 飞书同步功能验证测试")
    print("=" * 60)
    
    tests = [
        ("模块导入", test_imports),
        ("依赖包", test_dependencies), 
        ("配置", test_config),
        ("数据格式化器", test_data_formatter),
        ("CSV文件加载", test_csv_loading),
        ("主脚本", test_main_script)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} 测试出错: {e}")
    
    print("\\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！可以开始使用飞书同步功能")
        print("\\n📖 下一步操作：")
        print("1. 配置 .env 文件（如未配置）")
        print("2. 运行: python sync_to_feishu.py --setup")
        print("3. 运行: python sync_to_feishu.py --file your_data_file.csv")
    else:
        print(f"⚠️  有 {total - passed} 个测试未通过，请检查相关问题")
        if passed < 2:  # 如果基础功能都有问题
            print("\\n🔧 建议操作：")
            print("1. 安装缺失的依赖包")
            print("2. 检查代码文件是否完整")
            print("3. 配置环境变量")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
