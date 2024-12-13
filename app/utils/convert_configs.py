import os
import sys
import json
import importlib.util
from typing import Dict, Any
from pathlib import Path

def setup_python_path():
    """设置Python路径以支持正确的模块导入"""
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 获取src目录路径
    src_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    # 获取crawlers目录的父目录
    crawlers_parent = os.path.dirname(os.path.dirname(current_dir))
    
    # 将必要的路径添加到Python路径
    paths_to_add = [src_dir, crawlers_parent]
    for path in paths_to_add:
        if path not in sys.path:
            sys.path.insert(0, path)
            print(f"Added path to sys.path: {path}")

def import_module_directly(module_path: str, module_name: str):
    """直接导入模块，不依赖包结构"""
    print(f"\nTrying to import module: {module_name}")
    print(f"Module path: {module_path}")
    
    try:
        # 导入base模块
        base_path = os.path.join(os.path.dirname(module_path), "base.py")
        print(f"Importing base module from: {base_path}")
        base_spec = importlib.util.spec_from_file_location("base", base_path)
        base_module = importlib.util.module_from_spec(base_spec)
        sys.modules["base"] = base_module
        base_spec.loader.exec_module(base_module)
        print("Successfully imported base module")
        
        # 导入目标模块
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        
        # 设置模块的内置变量
        module.__package__ = "crawlers.site_config"
        module.__file__ = module_path
        
        # 执行模块
        spec.loader.exec_module(module)
        print(f"Successfully imported module: {module_name}")
        
        return module
        
    except Exception as e:
        print(f"Error during module import: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise

def convert_py_to_json():
    """将Python配置文件转换为JSON格式"""
    # 获取当前目录（Python配置文件目录）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"\nScanning directory for Python configs: {current_dir}")
    
    # 获取目标JSON配置目录
    src_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    target_dir = os.path.join(src_dir, "config", "site")
    print(f"Target directory for JSON configs: {target_dir}")
    
    # 确保目标目录存在
    os.makedirs(target_dir, exist_ok=True)
    
    # 获取所有Python文件
    py_files = [f for f in os.listdir(current_dir) 
                if f.endswith('.py') and 
                not f.startswith(('__', 'base', 'convert'))]
    print(f"Found {len(py_files)} Python files to convert: {py_files}")
    
    # 遍历目录中的所有Python文件
    for filename in py_files:
        print(f"\nProcessing file: {filename}")
        try:
            # 构建模块路径
            module_path = os.path.join(current_dir, filename)
            module_name = filename[:-3]
            
            # 直接导入模块
            module = import_module_directly(module_path, module_name)
            
            # 查找配置类
            config_class_name = f"{module_name.capitalize()}Config"
            print(f"Looking for config class: {config_class_name}")
            
            if hasattr(module, config_class_name):
                config_class = getattr(module, config_class_name)
                print(f"Found config class: {config_class}")
                
                # 获取配置
                print("Getting config from class...")
                config = config_class.get_config()
                
                # 创建JSON文件
                json_filename = f"{module_name}.json"
                json_path = os.path.join(target_dir, json_filename)
                
                # 写入JSON文件
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=4)
                    
                print(f"Successfully converted {filename} to {json_filename}")
                
            else:
                print(f"Warning: Could not find config class {config_class_name} in {filename}")
                print(f"Available attributes: {dir(module)}")
                
        except Exception as e:
            print(f"Error converting {filename}: {str(e)}")
            import traceback
            print(traceback.format_exc())

def validate_json_files():
    """验证生成的JSON文件"""
    # 获取JSON配置目录
    src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    config_dir = os.path.join(src_dir, "config", "site")
    print(f"\nValidating JSON files in: {config_dir}")
    
    json_files = [f for f in os.listdir(config_dir) if f.endswith('.json')]
    print(f"Found {len(json_files)} JSON files to validate")
    
    for filename in json_files:
        print(f"\nValidating {filename}...")
        try:
            # 读取JSON文件
            with open(os.path.join(config_dir, filename), 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 验证必要字段
            required_fields = ['site_id', 'site_url']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                print(f"Warning: {filename} is missing required fields: {missing_fields}")
            else:
                print(f"Validated {filename}: OK")
                
        except Exception as e:
            print(f"Error validating {filename}: {str(e)}")
            import traceback
            print(traceback.format_exc())

def main():
    """主函数"""
    print("Starting conversion process...")
    print("Setting up Python path...")
    setup_python_path()
    
    print("\nStarting configuration conversion...")
    convert_py_to_json()
    
    print("\nValidating generated JSON files...")
    validate_json_files()
    
    print("\nConversion completed.")

if __name__ == "__main__":
    main() 