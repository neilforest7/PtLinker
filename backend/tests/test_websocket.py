import asyncio
import websockets
import json
from datetime import datetime
import uuid

async def test_crawler_websocket():
    """测试爬虫 WebSocket 连接"""
    uri = 'ws://localhost:8000/ws/crawler'
    async with websockets.connect(uri) as websocket:
        # 发送认证消息
        auth_message = {
            'type': 'auth',
            'crawler_id': 'test_crawler',
            'timestamp': datetime.utcnow().isoformat()
        }
        await websocket.send(json.dumps(auth_message))
        print('发送认证消息')
        
        # 接收认证响应
        response = await websocket.recv()
        print('认证响应:', response)
        
        # 发送心跳
        heartbeat = {
            'type': 'heartbeat',
            'timestamp': datetime.utcnow().isoformat()
        }
        await websocket.send(json.dumps(heartbeat))
        print('发送心跳')
        
        # 接收心跳响应
        response = await websocket.recv()
        print('心跳响应:', response)

async def test_task_websocket():
    """测试任务 WebSocket 连接"""
    task_id = str(uuid.uuid4())
    uri = f'ws://localhost:8000/ws/task/{task_id}'
    async with websockets.connect(uri) as websocket:
        print(f'已连接到任务 WebSocket: {task_id}')
        
        # 等待状态更新
        response = await websocket.recv()
        print('任务状态:', response)

async def test_task_lifecycle():
    """测试完整的任务生命周期"""
    # 连接爬虫 WebSocket
    crawler_ws = await websockets.connect('ws://localhost:8000/ws/crawler')
    
    try:
        # 认证
        auth_message = {
            'type': 'auth',
            'crawler_id': 'test_crawler',
            'timestamp': datetime.utcnow().isoformat()
        }
        await crawler_ws.send(json.dumps(auth_message))
        response = await crawler_ws.recv()
        print('爬虫认证完成')
        
        # 模拟任务执行
        task_id = str(uuid.uuid4())
        
        # 发送任务开始状态
        start_message = {
            'type': 'status',
            'status': 'task_received',
            'data': {
                'task_id': task_id,
                'timestamp': datetime.utcnow().isoformat()
            }
        }
        await crawler_ws.send(json.dumps(start_message))
        print('发送任务开始状态')
        
        # 发送一些日志
        log_message = {
            'type': 'log',
            'data': {
                'level': 'info',
                'message': '测试日志消息',
                'metadata': {
                    'task_id': task_id,
                    'crawler_id': 'test_crawler'
                }
            }
        }
        await crawler_ws.send(json.dumps(log_message))
        print('发送日志消息')
        
        # 等待一会儿
        await asyncio.sleep(2)
        
        # 发送任务完成状态
        complete_message = {
            'type': 'status',
            'status': 'task_completed',
            'data': {
                'task_id': task_id,
                'timestamp': datetime.utcnow().isoformat(),
                'result': {
                    'success': True,
                    'items_processed': 10
                }
            }
        }
        await crawler_ws.send(json.dumps(complete_message))
        print('发送任务完成状态')
        
    finally:
        await crawler_ws.close()

async def main():
    """运行所有测试"""
    print('=== 开始测试 WebSocket 功能 ===')
    
    print('\n1. 测试爬虫 WebSocket 连接')
    await test_crawler_websocket()
    
    print('\n2. 测试任务 WebSocket 连接')
    await test_task_websocket()
    
    print('\n3. 测试任务生命周期')
    await test_task_lifecycle()
    
    print('\n=== 测试完成 ===')

if __name__ == '__main__':
    asyncio.run(main()) 