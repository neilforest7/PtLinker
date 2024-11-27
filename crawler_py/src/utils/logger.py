from loguru import logger
import sys
from pathlib import Path
from config.settings import settings

def setup_logger():
    """配置日志"""
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>",
        level="INFO"
    )
    
    # 添加文件处理器
    log_dir = settings.BASE_DIR / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        log_dir / "crawler_{time}.log",
        rotation="500 MB",
        retention="10 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
                "{name}:{function}:{line} | {message}",
        level="DEBUG"
    )
    
    # 添加错误日志处理器
    logger.add(
        log_dir / "error_{time}.log",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
                "{name}:{function}:{line} | {message}",
        level="ERROR"
    )

def get_logger(name: str):
    """获取日志记录器"""
    return logger.bind(name=name)