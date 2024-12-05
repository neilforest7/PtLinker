from loguru import logger
import sys
from pathlib import Path
from typing import Optional

def setup_logger():
    """配置日志系统"""
    # 移除默认处理器
    logger.remove()
    
    # 日志格式
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}:{function}:{line}</cyan> | "
        "{extra[service]} | "
        "{extra[task_id]} | "
        "{extra[crawler_id]} | "
        "<level>{message}</level>"
    )
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format=log_format,
        level="INFO",
        colorize=True,
        enqueue=True,
        backtrace=True,
        diagnose=True
    )
    
    # 添加文件处理器 - 所有日志
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)
    
    logger.add(
        log_path / "backend.log",
        format=log_format,
        level="DEBUG",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=True
    )
    
    # 添加文件处理器 - 仅错误日志
    logger.add(
        log_path / "error.log",
        format=log_format,
        level="ERROR",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=True,
        filter=lambda record: record["level"].name == "ERROR"
    )
    
    return logger

# 全局日志实例
logger = setup_logger() 

def get_logger(service: Optional[str] = None, task_id: Optional[str] = None, crawler_id: Optional[str] = None):
    """获取日志实例"""
    return logger.bind(service=service, task_id=task_id, crawler_id=crawler_id)
