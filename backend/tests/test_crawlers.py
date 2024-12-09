import asyncio
import aiohttp
import json
import logging
from datetime import datetime
import websockets
from typing import Dict, Any, Optional
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.logger import get_logger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrawlerTest:
    def __init__(self):
        self.api_base = "http://localhost:8000/api/v1"
        self.ws_base = "ws://localhost:8000/ws"
        self.task_websockets: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.task_results: Dict[str, Dict[str, Any]] = {}

    async def wait_for_crawler_ready(self, crawler_id: str, timeout: int = 30) -> bool:
        """等待爬虫服务就绪"""
        logger_ctx = get_logger(service="test_crawler", crawler_id=crawler_id)
        print('开始运行等待爬虫就绪函数')
        start_time = time.time()
        print(f'等待爬虫就绪starttime: {start_time}')
        while time.time() - start_time < timeout:
            print(f'time.time() - start_time: {time.time() - start_time}')
            try:
                async with aiohttp.ClientSession() as session:
                    url = f'{self.api_base}/crawlers/{crawler_id}/status'
                    print(f"Checking crawler status at: {url}")
                    async with session.get(url) as response:
                        print(f'首次爬虫状态响应: {response}')
                        if response.status == 200:
                            data = await response.json()
                            print(f'爬虫状态响应: {data}')
                            
                            is_connected = data.get("is_connected", False)
                            status = data.get("status", "unknown")
                            
                            if is_connected and status == "ready":
                                logger_ctx.info(f'爬虫已就绪 (connected: {is_connected}, status: {status})')
                                return True
                            else:
                                print(f'爬虫未就绪 (connected: {is_connected}, status: {status})')
                        else:
                            logger_ctx.warning(f'获取爬虫状态失败: HTTP {response.status}')
                            
                await asyncio.sleep(1)
            except Exception as e:
                logger_ctx.error(f'检查爬虫状态出错: {str(e)}', exc_info=True)
                await asyncio.sleep(1)
        
        logger_ctx.error(f'等待爬虫就绪超时')
        return False

    async def create_task(self, crawler_id: str) -> Optional[str]:
        """创建爬虫任务"""
        # 首先等待爬虫就绪
        if not await self.wait_for_crawler_ready(crawler_id):
            logger.error(f'爬虫 {crawler_id} 未就绪，无法创建任务')
            return None

        async with aiohttp.ClientSession() as session:
            task_data = {
                "crawler_id": crawler_id
            }
            
            try:
                async with session.post(f'{self.api_base}/tasks', json=task_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        task_id = result.get('task_id')
                        print(f'创建任务成功: {crawler_id}, task_id: {task_id}')
                        return task_id
                    else:
                        error = await response.text()
                        logger.error(f'创建任务失败: {error}')
                        return None
            except Exception as e:
                logger.error(f'创建任务出错: {str(e)}')
                return None

    async def monitor_task(self, task_id: str):
        """监控任务状态"""
        try:
            ws = await websockets.connect(f'{self.ws_base}/task/{task_id}')
            self.task_websockets[task_id] = ws
            print(f'开始监控任务: {task_id}')
            
            while True:
                try:
                    message = await ws.recv()
                    data = json.loads(message)
                    message_type = data.get('type')
                    
                    if message_type == 'status':
                        status = data.get('data', {}).get('status')
                        print(f'任务 {task_id} 状态更新: {status}')
                        
                        if status in ['success', 'failed', 'cancelled']:
                            self.task_results[task_id] = data.get('data', {})
                            break
                    
                    elif message_type == 'log':
                        log_data = data.get('data', {})
                        print(f'任务日志: [{log_data.get("level", "info")}] {log_data.get("message", "")}')
                
                except websockets.ConnectionClosed:
                    logger.warning(f'任务 {task_id} 监控连接已关闭')
                    break
                except Exception as e:
                    logger.error(f'监控任务出错: {str(e)}')
                    break
            
        except Exception as e:
            logger.error(f'连接任务监控失败: {str(e)}')
        finally:
            if task_id in self.task_websockets:
                await self.task_websockets[task_id].close()
                del self.task_websockets[task_id]

    async def run_crawler_test(self, crawler_id: str):
        """运行单个爬虫测试"""
        # 创建任务
        print()
        task_id = await self.create_task(crawler_id)
        print(f'创建任务: {task_id}')
        if not task_id:
            return False
        
        # 监控任务
        monitor_task = asyncio.create_task(self.monitor_task(task_id))
        print(f'监控任务: {task_id}')
        
        # 等待任务完成
        await monitor_task
        print(f'任务完成: {task_id}')
        
        # 检查结果
        result = self.task_results.get(task_id, {})
        print(f'任务结果: {result}')
        status = result.get('status')
        print(f'任务状态: {status}')
        if status == 'success':
            print(f'爬虫 {crawler_id} 测试成功')
            return True
        else:
            error = result.get('error', '未知错误')
            logger.error(f'爬虫 {crawler_id} 测试失败: {error}')
            return False

    async def cleanup(self):
        """清理资源"""
        for ws in self.task_websockets.values():
            await ws.close()
        self.task_websockets.clear()
        self.task_results.clear()

async def main():
    """运行爬虫测试"""
    test = CrawlerTest()
    
    try:
        print("=== 开始爬虫测试 ===")
        
        # 运行测试
        print("\n1. 测试 HDFans 爬虫")
        hdfans_success = await test.run_crawler_test("hdfans")
        
        print("\n2. 测试 ZMPT 爬虫")
        zmpt_success = await test.run_crawler_test("zmpt")
        
        # 输出结果汇总
        print("\n=== 测试结果汇总 ===")
        print(f"HDFans: {'成功' if hdfans_success else '失败'}")
        print(f"ZMPT: {'成功' if zmpt_success else '失败'}")
        
    finally:
        await test.cleanup()

if __name__ == '__main__':
    asyncio.run(main()) 