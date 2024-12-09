from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, Any
from app.core.logger import get_logger
from app.services.websocket_manager import manager
from app.services.crawler_manager import crawler_manager
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.database import get_db
from app.models.task import Task, TaskStatus

router = APIRouter()
logger = get_logger(service="websocket")

@router.websocket("/ws/crawler")
async def crawler_websocket(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db)
):
    """处理爬虫服务的 WebSocket 连接"""
    await websocket.accept()
    crawler_id = None
    
    try:
        # 等待爬虫服务发送身份验证消息
        auth_message = await websocket.receive_json()
        logger.debug(f"Received auth message: {auth_message}")
        
        crawler_id = auth_message.get("crawler_id")
        if not crawler_id:
            logger.error("Missing crawler_id in auth message")
            await websocket.close(code=4000, reason="Missing crawler_id")
            return
            
        # 注册连接
        await manager.connect(crawler_id, websocket)
        logger.info(f"Crawler {crawler_id} connected")
        
        # 发送确认消息
        await websocket.send_json({
            "type": "auth",
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # 消息处理循环
        while True:
            message = await websocket.receive_json()
            logger.debug(f"Received message from {crawler_id}: {message}")
            message_type = message.get("type")
            
            if message_type == "status":
                await process_crawler_status(message, logger, db)
            elif message_type == "log":
                await process_crawler_log(message, logger)
            elif message_type == "heartbeat":
                await process_heartbeat(message, crawler_id, websocket)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
    except WebSocketDisconnect:
        logger.info(f"Crawler {crawler_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
    finally:
        if crawler_id:
            await manager.disconnect(crawler_id)
            logger.info(f"Crawler {crawler_id} disconnected")

@router.websocket("/ws/task/{task_id}")
async def task_websocket(
    websocket: WebSocket, 
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """处理任务监控的 WebSocket 连接"""
    await websocket.accept()
    logger.info(f"Task monitor connected for task {task_id}")
    
    try:
        # 注册任务连接
        await manager.connect_task(task_id, websocket)
        
        # 发送当前任务状态
        await manager.send_task_status(task_id, db)
        
        # 保持连接直到客户端断开
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        logger.info(f"Task monitor disconnected for task {task_id}")
    except Exception as e:
        logger.error(f"Task WebSocket error: {str(e)}", exc_info=True)
    finally:
        await manager.disconnect_task(task_id)

async def process_crawler_status(message: dict, logger, db: AsyncSession):
    """处理爬虫状态消息"""
    try:
        status = message.get("status")
        data = message.get("data", {})
        
        # 处理服务状态更新
        if status == "service_status":
            crawler_id = data.get("crawler_id")
            if crawler_id:
                # 更新爬虫状态
                status_data = {
                    "is_connected": True,
                    "status": data.get("status", "unknown"),
                    "last_updated": datetime.utcnow().isoformat()
                }
                await crawler_manager.update_crawler_status(crawler_id, status_data)
                logger.debug(f"Updated service status for crawler {crawler_id}: {status_data}")
            return
            
        # 处理任务状态更新
        task_id = data.get("task_id")
        if not task_id:
            logger.warning("Received task status update without task_id")
            return
            
        logger.info(f"Task {task_id} status update: {status}", extra=data)
        
        # 处理不同类型的状态更新
        if status == "task_started":
            # 更新任务开始时间
            stmt = update(Task).where(Task.task_id == task_id).values(
                status=TaskStatus.RUNNING,
                started_at=datetime.utcnow()
            )
            await db.execute(stmt)
            await db.commit()
            await manager.send_status(task_id, "running", data)
            
        elif status == "task_completed":
            # 更新任务状态和完成时间
            stmt = update(Task).where(Task.task_id == task_id).values(
                status=TaskStatus.SUCCESS,
                completed_at=datetime.utcnow()
            )
            await db.execute(stmt)
            await db.commit()
            await manager.send_status(task_id, "success", data)
            
        elif status == "task_failed":
            # 更新任务状态、错误信息和完成时间
            stmt = update(Task).where(Task.task_id == task_id).values(
                status=TaskStatus.FAILED,
                completed_at=datetime.utcnow(),
                error=data.get("error", "Unknown error")
            )
            await db.execute(stmt)
            await db.commit()
            await manager.send_status(task_id, "failed", data)
            
        elif status == "task_cancelled":
            # 更新任务状态和完成时间
            stmt = update(Task).where(Task.task_id == task_id).values(
                status=TaskStatus.CANCELLED,
                completed_at=datetime.utcnow(),
                error="Task cancelled"
            )
            await db.execute(stmt)
            await db.commit()
            await manager.send_status(task_id, "cancelled", data)
            
        else:
            await manager.send_status(task_id, status, data)
                
    except Exception as e:
        logger.error(f"Error processing crawler status: {str(e)}", exc_info=True)

async def process_crawler_log(message: dict, logger):
    """处理爬虫日志消息"""
    try:
        data = message.get("data", {})
        level = data.get("level", "info")
        log_message = data.get("message", "")
        metadata = data.get("metadata", {})
        task_id = metadata.get("task_id")
        
        # 记录日志
        log_func = getattr(logger, level, logger.info)
        log_func(log_message, extra=metadata)
        
        # 如果有任务ID，转发日志到相应的任务WebSocket
        if task_id:
            await manager.send_log(task_id, level, log_message, metadata)
            
    except Exception as e:
        logger.error(f"Error processing crawler log: {str(e)}", exc_info=True)

async def process_heartbeat(message: dict, crawler_id: str, websocket: WebSocket):
    """处理心跳消息"""
    try:
        await websocket.send_json({
            "type": "heartbeat",
            "status": "pong",
            "timestamp": datetime.utcnow().isoformat(),
            "crawler_id": crawler_id
        })
    except Exception as e:
        logger.error(f"Error processing heartbeat: {str(e)}", exc_info=True)