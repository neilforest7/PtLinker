from typing import List, Dict, Any, Optional
from datetime import datetime
from app.schemas.crawler import CrawlerInfo, CrawlerStatus
from app.core.config import get_settings
from app.core.logger import get_logger
from app.services.websocket_manager import manager

class CrawlerManager:
    def __init__(self):
        self.logger = get_logger(service="crawler_manager")
        self.settings = get_settings()
        self._crawler_statuses: Dict[str, Dict[str, Any]] = {}
        self._available_crawlers = [
            'ubits', 'ourbits', 'qingwapt', 'frds', 'hdhome', 
            'audiences', 'rousi', 'kylin', 'hdatoms', 'haidan', 
            'nicept', 'btschool', 'carpt', 'zmpt', 'u2', 'iloli', 'hdpt'
        ]
        self.logger.debug("Crawler manager initialized")

    def get_available_crawlers(self) -> List[str]:
        """获取所有可用的爬虫配置"""
        try:
            self.logger.info(f"Found {len(self._available_crawlers)} available crawlers")
            return self._available_crawlers
        except Exception as e:
            self.logger.error(f"Failed to get available crawlers: {str(e)}", exc_info=True)
            return []

    def get_crawler_info(self, crawler_id: str) -> Optional[CrawlerInfo]:
        """获取爬虫基本信息"""
        try:
            if crawler_id not in self._available_crawlers:
                self.logger.warning(f"Crawler not found: {crawler_id}")
                return None

            crawler_info = CrawlerInfo(
                crawler_id=crawler_id,
                name=crawler_id.upper(),
                description=f"{crawler_id.upper()} PT站点",
                site_id=crawler_id
            )
            
            self.logger.debug(f"Got crawler info: {crawler_id}")
            return crawler_info

        except Exception as e:
            self.logger.error(f"Failed to get crawler info {crawler_id}: {str(e)}", exc_info=True)
            return None

    async def get_crawler_status(self, crawler_id: str) -> Dict[str, Any]:
        """获取爬虫状态"""
        try:
            if crawler_id not in self._crawler_statuses:
                return {
                    "is_connected": False,
                    "status": "disconnected",
                    "last_updated": datetime.now().isoformat(),
                    "connected_at": None,
                    "disconnected_at": datetime.now().isoformat(),
                    "error": None
                }
            return self._crawler_statuses[crawler_id]
        except Exception as e:
            self.logger.error(f"Failed to get crawler status {crawler_id}: {str(e)}", exc_info=True)
            return {
                "is_connected": False,
                "status": "error",
                "last_updated": datetime.now().isoformat(),
                "error": str(e)
            }

    async def update_crawler_status(self, crawler_id: str, status_data: Dict[str, Any]) -> None:
        """更新爬虫状态"""
        try:
            current_time = datetime.now().isoformat()
            
            # 如果状态不存在，初始化它
            if crawler_id not in self._crawler_statuses:
                self._crawler_statuses[crawler_id] = {
                    "is_connected": False,
                    "status": "unknown",
                    "last_updated": current_time,
                    "connected_at": None,
                    "disconnected_at": None,
                    "error": None
                }
            
            # 更新状态
            status = self._crawler_statuses[crawler_id]
            status.update(status_data)
            status["last_updated"] = current_time
            
            # 处理连接状态变化
            if status_data.get("is_connected", False):
                if not status.get("connected_at"):
                    status["connected_at"] = current_time
                status["disconnected_at"] = None
            else:
                if not status.get("disconnected_at"):
                    status["disconnected_at"] = current_time
            
            # 广播状态更新
            await manager.broadcast_status(crawler_id, status)
            
            self.logger.debug(f"Updated crawler status: {crawler_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to update crawler status {crawler_id}: {str(e)}", exc_info=True)

    async def list_crawlers(self) -> List[Dict[str, Any]]:
        """获取所有爬虫的状态列表"""
        try:
            crawler_ids = self.get_available_crawlers()
            crawler_list = []
            
            for crawler_id in crawler_ids:
                try:
                    # 获取爬虫状态
                    status = await self.get_crawler_status(crawler_id)
                    
                    # 组合信息
                    crawler_info = {
                        "crawler_id": crawler_id,
                        "name": crawler_id.upper(),
                        "description": f"{crawler_id.upper()} PT站点",
                        "site_id": crawler_id,
                        "is_connected": status.get("is_connected", False),
                        "status": status.get("status", "unknown"),
                        "last_updated": status.get("last_updated"),
                        "connected_at": status.get("connected_at"),
                        "disconnected_at": status.get("disconnected_at"),
                        "error": status.get("error")
                    }
                    crawler_list.append(crawler_info)
                    
                except Exception as e:
                    self.logger.error(f"Error getting info for crawler {crawler_id}: {str(e)}")
                    continue
            
            self.logger.info(f"Listed {len(crawler_list)} crawlers")
            return crawler_list
            
        except Exception as e:
            self.logger.error(f"Failed to list crawlers: {str(e)}")
            raise

# 全局爬虫管理器实例
crawler_manager = CrawlerManager()
