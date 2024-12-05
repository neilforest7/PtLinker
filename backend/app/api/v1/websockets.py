from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.websocket_manager import manager
from app.models.task import Task
from sqlalchemy import select
from app.core.logger import get_logger
import json
from datetime import datetime
import sys

# # 配置loguru
# logger.remove()  # 移除默认的处理器
# # 添加带有颜色的控制台处理器
# logger.add(
#     sys.stdout,
#     format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[task_id]}</cyan> - <white>{message}</white>",
#     colorize=True,
#     enqueue=True
# )

router = APIRouter(tags=["websockets"])
_logger = get_logger(service="websocket_api")

async def process_logs(logs: list, task_id: str):
    """处理接收到的日志消息"""
    logger_ctx = get_logger(task_id=task_id)
    for log in logs:
        try:
            data = log.get("data", {})
            level = data.get("level", "info")
            message = data.get("message", "")
            metadata = data.get("metadata", {})
            
            # 使用loguru记录日志
            log_func = getattr(logger_ctx, level)
            log_func(
                message,
                site_id=metadata.get("site_id", "unknown"),
                function=metadata.get("function", ""),
                line=metadata.get("line", 0),
                file=metadata.get("file", "")
            )
            
        except Exception as e:
            logger_ctx.error(f"Error processing log message: {str(e)}", exc_info=True)

@router.websocket("/ws/tasks/{task_id}")
async def websocket_task_endpoint(
    websocket: WebSocket,
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    logger_ctx = get_logger(task_id=task_id)
    
    # 验证任务是否存在
    result = await db.execute(select(Task).filter(Task.task_id == task_id))
    task = result.scalar_one_or_none()
    
    if task is None:
        logger_ctx.warning("Task not found, closing WebSocket connection")
        await websocket.close(code=4004, reason="Task not found")
        return
    
    # 建立连接
    await manager.connect(websocket, task_id)
    logger_ctx.info("WebSocket connection established")
    
    try:
        # 发送初始状态
        await manager.send_status(task_id, str(task.status))
        
        # 保持连接并等待消息
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_text()
                logger_ctx.debug("Received message from client")
                
                # 解析并处理日志消息
                try:
                    logs = json.loads(data)
                    if isinstance(logs, list):
                        await process_logs(logs, task_id)
                    elif isinstance(logs, dict):
                        await process_logs([logs], task_id)
                except json.JSONDecodeError:
                    logger_ctx.error(f"Invalid JSON received: {data}")
                    
            except WebSocketDisconnect:
                logger_ctx.info("WebSocket connection closed by client")
                break
            except Exception as e:
                logger_ctx.error(f"WebSocket error: {str(e)}", exc_info=True)
                break
    
    finally:
        # 断开连接时清理
        await manager.disconnect(websocket, task_id)
        logger_ctx.info("WebSocket connection cleaned up") 