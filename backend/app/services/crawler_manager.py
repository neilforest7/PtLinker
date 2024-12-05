import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.schemas.crawler import CrawlerConfig, CrawlerInfo
from app.core.config import get_settings
from app.core.logger import get_logger

class CrawlerManager:
    def __init__(self):
        self.logger = get_logger(service="crawler_manager")
        self.settings = get_settings()
        self.config_dir = self.settings.CRAWLER_CONFIG_PATH
        self.logger.debug(f"Initialized with config directory: {self.config_dir}")

    def get_available_crawlers(self) -> List[str]:
        """获取所有可用的爬虫配置"""
        try:
            # 获取配置目录下的所有.json文件
            crawler_files = list(self.config_dir.glob("*.json"))
            crawler_ids = [f.stem for f in crawler_files]
            self.logger.info(f"Found {len(crawler_ids)} available crawlers")
            return crawler_ids
        except Exception as e:
            self.logger.error(f"Failed to get available crawlers: {str(e)}", exc_info=True)
            return []

    def get_crawler_config(self, crawler_id: str) -> Optional[CrawlerConfig]:
        """获取特定爬虫的配置"""
        config_path = self.config_dir / f"{crawler_id}.json"
        try:
            if not config_path.exists():
                self.logger.warning(f"Crawler config not found: {crawler_id}")
                return None

            self.logger.debug(f"Loading crawler config: {crawler_id}")
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                return CrawlerConfig(**config_data)

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in crawler config {crawler_id}: {str(e)}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"Failed to load crawler config {crawler_id}: {str(e)}", exc_info=True)
            return None

    def save_crawler_config(self, crawler_id: str, config: CrawlerConfig) -> bool:
        """保存爬虫配置"""
        config_path = self.config_dir / f"{crawler_id}.json"
        try:
            self.logger.info(f"Saving crawler config: {crawler_id}")
            config_data = config.dict(exclude_none=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"Crawler config saved successfully: {crawler_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save crawler config {crawler_id}: {str(e)}", exc_info=True)
            return False

    def delete_crawler_config(self, crawler_id: str) -> bool:
        """删除爬虫配置"""
        config_path = self.config_dir / f"{crawler_id}.json"
        try:
            if not config_path.exists():
                self.logger.warning(f"Crawler config not found for deletion: {crawler_id}")
                return False

            self.logger.info(f"Deleting crawler config: {crawler_id}")
            config_path.unlink()
            self.logger.debug(f"Crawler config deleted successfully: {crawler_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete crawler config {crawler_id}: {str(e)}", exc_info=True)
            return False

# 全局爬虫管理器实例
crawler_manager = CrawlerManager()
