import importlib

def import_string(dotted_path: str):
    """
    从点分路径导入模块或对象
    
    Args:
        dotted_path: 模块路径，如 "app.services.sites.example.crawler"
        
    Returns:
        导入的模块或对象
        
    Raises:
        ImportError: 如果导入失败
    """
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError as e:
        raise ImportError("%s doesn't look like a module path" % dotted_path) from e

    try:
        return importlib.import_module(module_path)
    except ImportError as e:
        raise ImportError('Failed to import %s' % dotted_path) from e 