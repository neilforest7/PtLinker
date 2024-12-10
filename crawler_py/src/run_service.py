import asyncio
import argparse
from service import CrawlerService
from utils.logger import setup_logger, get_logger

async def main():
    # 设置日志
    setup_logger()
    logger = get_logger(__name__)
    
    try:
        # 创建并启动爬虫服务（现在会自动启动所有站点）
        service = CrawlerService()
        logger.info("Starting crawler service for all sites")
        await service.start()
        
        # 保持服务运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Service error: {str(e)}")
    finally:
        if 'service' in locals():
            await service.stop()
        logger.info("Service stopped")

if __name__ == "__main__":
    asyncio.run(main()) 