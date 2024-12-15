import os
import sys
from pathlib import Path

from loguru import logger

_logger = None

def setup_logger(is_subprocess: bool = False):
    global _logger
    if _logger is not None:
        return _logger
        
    _logger = logger.bind(site_id="main")
    # 从环境变量读取配置
    BASE_DIR = Path(__file__).parent.parent.parent
    log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()
    console_log_level = os.getenv('CONSOLE_LOG_LEVEL', log_level).upper()
    file_log_level = os.getenv('FILE_LOG_LEVEL', 'DEBUG').upper()
    error_log_level = os.getenv('ERROR_LOG_LEVEL', 'ERROR').upper()
    
    # 日志文件配置
    log_dir = Path(os.getenv('LOG_DIR', BASE_DIR / 'app'/'logs'))
    log_file = os.getenv('LOG_FILE', 'crawler_{time:YYMMDD-HHMMSS}.log')
    error_log_file = os.getenv('ERROR_LOG_FILE', 'error_{time:YYMMDD-HHMMSS}.log')
    
    # 日志保留配置
    log_rotation = os.getenv('LOG_ROTATION', '500 MB')
    log_retention = os.getenv('LOG_RETENTION', '10 days')
    error_log_rotation = os.getenv('ERROR_LOG_ROTATION', '100 MB')
    error_log_retention = os.getenv('ERROR_LOG_RETENTION', '30 days')    
    
    # 移除默认处理器
    logger.remove()
    if not is_subprocess:
        # 添加控制台处理器（使用异步和队列）
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | "
                    "<level>{level: <8}</level> | "
                    "<blue>{extra[site_id]:<10}</blue> | "
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                    "<level>{message}</level>",
            level=console_log_level,
            colorize=True,
            enqueue=True,  # 启用队列模式
            catch=True,    # 捕获异常
            diagnose=True  # 禁用诊断信息以提高性能
        )
        
        # 确保日志目录存在
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 添加文件处理器（使用异步和队列）
        logger.add(
            log_dir / "logs" / log_file,
            rotation=log_rotation,
            retention=log_retention,
            compression="zip",
            colorize=True,
            format="{time:HH:mm:ss} | {level: <8} | "
                    "{extra[site_id]:<10} | "
                    "{name}:{function}:{line} | {message}",
            level=file_log_level,
            encoding="utf-8",
            enqueue=True, # 启用队列模式
            catch=True,        # 捕获异常
            diagnose=False,    # 禁用诊断信息以提高性能
            delay=True,        # 延迟创建文件直到第一次写入
            mode="a"          # 追加模式
        )
        
        # 添加错误日志处理器（使用异步和队列）
        logger.add(
            log_dir / "error" / error_log_file,
            rotation=error_log_rotation,
            retention=error_log_retention,
            compression="zip",
            colorize=True,
            format="{time:HH:mm:ss} | {level: <8} | "
                    "{extra[site_id]:<10} | "
                    "{name}:{function}:{line} | {message}",
            level=error_log_level,
            encoding="utf-8",
            enqueue=True,      # 启用队列模式
            catch=True,        # 捕获异常
            diagnose=False,    # 禁用诊断信息以提高性能
            delay=True,        # 延迟创建文件直到第一次写入
            mode="a"          # 追加模式
        )
    else:
        # 子进程只使用控制台输出，不写文件
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | "
                    "<level>{level: <8}</level> | "
                    "<blue>{extra[site_id]:<10}</blue> | "
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                    "<level>{message}</level>",
            level=console_log_level,
            colorize=True,
            enqueue=False,
            catch=True,
            diagnose=False
        )
    # 记录日志配置信息
    _logger.trace("日志配置已加载")
    _logger.trace(f"控制台日志级别: {console_log_level}")
    _logger.trace(f"文件日志级别: {file_log_level}")
    _logger.trace(f"错误日志级别: {error_log_level}")
    _logger.trace(f"日志目录: {log_dir}")
    _logger.trace(f"主日志文件: {log_file}")
    _logger.trace(f"错误日志文件: {error_log_file}")
    
    return _logger

def get_logger(name: str, site_id: str = "Unknown", is_subprocess: bool = False):
    if _logger is None:
        setup_logger(is_subprocess)
    return _logger.bind(name=name, site_id=site_id)