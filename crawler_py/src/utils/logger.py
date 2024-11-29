import os
import sys
from pathlib import Path

from loguru import logger


def setup_logger():
    """配置日志"""
    # 从环境变量读取配置
    BASE_DIR = Path(__file__).parent.parent.parent
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    console_log_level = os.getenv('CONSOLE_LOG_LEVEL', log_level).upper()
    file_log_level = os.getenv('FILE_LOG_LEVEL', 'DEBUG').upper()
    error_log_level = os.getenv('ERROR_LOG_LEVEL', 'ERROR').upper()
    
    # 日志文件配置
    log_dir = Path(os.getenv('LOG_DIR', BASE_DIR / 'logs'))
    log_file = os.getenv('LOG_FILE', 'crawler_{time:YYMMDD-HHMMSS}.log')
    error_log_file = os.getenv('ERROR_LOG_FILE', 'error_{time:YYMMDD-HHMMSS}.log')
    
    # 日志保留配置
    log_rotation = os.getenv('LOG_ROTATION', '500 MB')
    log_retention = os.getenv('LOG_RETENTION', '10 days')
    error_log_rotation = os.getenv('ERROR_LOG_ROTATION', '100 MB')
    error_log_retention = os.getenv('ERROR_LOG_RETENTION', '30 days')    
    
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<blue>{extra[site_id]:<8}</blue> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>",
        level=console_log_level,
        colorize=True
    )
    
    # 确保日志目录存在
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 添加文件处理器
    logger.add(
        log_dir / "logs" / log_file,
        rotation=log_rotation,
        retention=log_retention,
        compression="zip",
        colorize=True,
        format="{time:HH:mm:ss} | {level: <8} | "
                "{extra[site_id]:<8} | "
                "{name}:{function}:{line} | {message}",
        level=file_log_level,
        encoding="utf-8",
        enqueue=True,
        backtrace=True
    )
    
    # 添加错误日志处理器
    logger.add(
        log_dir / "error" / error_log_file,
        rotation=error_log_rotation,
        retention=error_log_retention,
        compression="zip",
        colorize=True,
        format="{time:HH:mm:ss} | {level: <8} | "
                "{extra[site_id]:<8} | "
                "{name}:{function}:{line} | {message}",
        level=error_log_level,
        encoding="utf-8",
        enqueue=True,
        backtrace=True
    )
    
    # 创建一个带有默认site_id的logger
    setup_logger = logger.bind(site_id="Setup")
    
    # 记录日志配置信息
    setup_logger.trace("日志配置已加载")
    setup_logger.trace(f"控制台日志级别: {console_log_level}")
    setup_logger.trace(f"文件日志级别: {file_log_level}")
    setup_logger.trace(f"错误日志级别: {error_log_level}")
    setup_logger.trace(f"日志目录: {log_dir}")
    setup_logger.trace(f"主日志文件: {log_file}")
    setup_logger.trace(f"错误日志文件: {error_log_file}")
    
    return logger

def get_logger(name: str, site_id: str = "Unknown"):
    """获取日志记录器"""
    return logger.bind(site_id=site_id)