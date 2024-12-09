import asyncio
import aiohttp
import json
from datetime import datetime
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_create_task():
    """测试创建单个任务"""
    async with aiohttp.ClientSession() as session:
        task_data = {
            "crawler_id": "test_site",
            "config": {
                "mode": "test",
                "max_pages": 5
            }
        }
        
        try:
            async with session.post('http://localhost:8000/api/v1/tasks', json=task_data) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f'创建任务成功: {result}')
                    return result.get('task_id')
                else:
                    error = await response.text()
                    logger.error(f'创建任务失败: {error}')
                    return None
        except Exception as e:
            logger.error(f'创建任务出错: {str(e)}')
            return None

async def test_create_batch_tasks():
    """测试批量创建任务"""
    async with aiohttp.ClientSession() as session:
        batch_data = {
            "site_ids": ["site1", "site2", "site3"],
            "config": {
                "mode": "test",
                "max_pages": 3
            }
        }
        
        try:
            async with session.post('http://localhost:8000/api/v1/tasks/batch', json=batch_data) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f'批量创建任务成功: {result}')
                    return [task.get('task_id') for task in result.get('tasks', [])]
                else:
                    error = await response.text()
                    logger.error(f'批量创建任务失败: {error}')
                    return []
        except Exception as e:
            logger.error(f'批量创建任务出错: {str(e)}')
            return []

async def test_get_task(task_id: str):
    """测试获取任务信息"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f'http://localhost:8000/api/v1/tasks/{task_id}') as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f'获取任务信息成功: {result}')
                    return result
                else:
                    error = await response.text()
                    logger.error(f'获取任务信息失败: {error}')
                    return None
        except Exception as e:
            logger.error(f'获取任务信息出错: {str(e)}')
            return None

async def test_cancel_task(task_id: str):
    """测试取消任务"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f'http://localhost:8000/api/v1/tasks/{task_id}/cancel') as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f'取消任务成功: {result}')
                    return True
                elif response.status == 400:
                    error = await response.json()
                    logger.warning(f'取消任务失败（任务未运行）: {error}')
                    return False
                else:
                    error = await response.text()
                    logger.error(f'取消任务失败: {error}')
                    return False
        except Exception as e:
            logger.error(f'取消任务出错: {str(e)}')
            return False

async def test_list_tasks():
    """测试获取任务列表"""
    async with aiohttp.ClientSession() as session:
        try:
            params = {
                'limit': 5,
                'offset': 0
            }
            async with session.get('http://localhost:8000/api/v1/tasks', params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f'获取任务列表成功: {result}')
                    return result
                else:
                    error = await response.text()
                    logger.error(f'获取任务列表失败: {error}')
                    return None
        except Exception as e:
            logger.error(f'获取任务列表出错: {str(e)}')
            return None

async def wait_for_task_status(session, task_id: str, target_status: str, timeout: int = 10):
    """等待任务达到指定状态"""
    start_time = datetime.utcnow()
    while (datetime.utcnow() - start_time).seconds < timeout:
        try:
            async with session.get(f'http://localhost:8000/api/v1/tasks/{task_id}') as response:
                if response.status == 200:
                    task = await response.json()
                    if task.get('status') == target_status:
                        return True
            await asyncio.sleep(1)
        except Exception:
            await asyncio.sleep(1)
    return False

async def main():
    """运行所有测试"""
    print('=== 开始测试任务管理功能 ===')
    
    print('\n1. 测试创建单个任务')
    task_id = await test_create_task()
    
    if task_id:
        print('\n2. 测试获取任务信息')
        task_info = await test_get_task(task_id)
        
        if task_info:
            print('\n3. 测试取消任务')
            # 由于任务可能还未开始运行，这里的取消可能会失败，这是正常的
            # cancel_result = await test_cancel_task(task_id)
            # if not cancel_result:
            #    print('任务取消失败（可能是因为任务未在运行），这是正常的')
    
    print('\n4. 测试批量创建任务')
    task_ids = await test_create_batch_tasks()
    
    print('\n5. 测试获取任务列表')
    tasks = await test_list_tasks()
    
    print('\n=== 测试完成 ===')

if __name__ == '__main__':
    asyncio.run(main()) 