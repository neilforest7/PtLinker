import asyncio
from datetime import datetime
from typing import Any, Dict

from app.api.websockets import manager
from app.core.config import settings
from app.services.data import DataService
from app.services.task import TaskService, TaskStatus
from playwright.async_api import async_playwright
from sqlalchemy.ext.asyncio import AsyncSession


class CrawlerService:
    def __init__(self):
        self.active_crawlers = {}
    
    async def start(self, task_id: str, config: Dict[str, Any], db_session: AsyncSession):
        task_service = TaskService(db_session)
        data_service = DataService(db_session)
        
        try:
            # 启动 playwright
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # 存储活跃的爬虫实例
            self.active_crawlers[task_id] = {
                'playwright': playwright,
                'browser': browser,
                'context': context,
                'page': page
            }
            
            # 更新任务状态为运行中
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=0
            )
            
            # 访问起始页面
            await page.goto(config['start_url'], timeout=settings.REQUEST_TIMEOUT * 1000)
            
            # 提取数据
            data = await self.extract_data(page, config['selectors'])
            
            # 存储数据
            await data_service.create_data(
                task_id=task_id,
                url=config['start_url'],
                data=data
            )
            
            # 更新任务状态为完成
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                progress=100
            )
            
        except Exception as e:
            # 更新任务状态为失败
            await task_service.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(e)
            )
            raise
        finally:
            # 清理资源
            await self.cleanup_crawler(task_id)
    
    async def extract_data(self, page, selectors: Dict[str, str]) -> Dict[str, Any]:
        data = {}
        
        for key, selector in selectors.items():
            try:
                element = await page.query_selector(selector)
                if element:
                    data[key] = await element.text_content()
                else:
                    data[key] = None
            except Exception as e:
                data[key] = f"Error: {str(e)}"
        
        return data
    
    async def cleanup_crawler(self, task_id: str):
        if task_id in self.active_crawlers:
            crawler = self.active_crawlers[task_id]
            await crawler['page'].close()
            await crawler['context'].close()
            await crawler['browser'].close()
            await crawler['playwright'].stop()
            del self.active_crawlers[task_id]
    
    async def cleanup(self):
        for task_id in list(self.active_crawlers.keys()):
            await self.cleanup_crawler(task_id) 