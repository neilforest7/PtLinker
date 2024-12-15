from datetime import datetime
from typing import Dict, List, Optional

from core.logger import get_logger
from models.models import BrowserState as DBBrowserState
from schemas.browserstate import BrowserState
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class BrowserStateManager:
    """浏览器状态管理器"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.logger = get_logger(name=__name__, site_id="BrowserStateMgr")
            self._session = None
            BrowserStateManager._initialized = True
            
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def initialize(self, session: AsyncSession) -> None:
        """初始化管理器"""
        self._session = session
        self.logger.info("BrowserStateManager initialized")
        
    @property
    def session(self) -> AsyncSession:
        if not self._session:
            raise RuntimeError("BrowserStateManager not initialized. Call initialize() first.")
        return self._session
        
    async def save_state(self, site_id: str, state: BrowserState) -> Optional[DBBrowserState]:
        """保存浏览器状态"""
        try:
            # 验证状态数据
            is_valid, error_msg = state.validate_state()
            if not is_valid:
                self.logger.error(f"浏览器状态数据无效: {error_msg}")
                return None
                
            # 检查是否存在现有记录
            stmt = select(DBBrowserState).where(DBBrowserState.site_id == site_id)
            result = await self.session.execute(stmt)
            db_state = result.scalar_one_or_none()
            
            if db_state:
                # 更新现有记录
                db_state.cookies = state.cookies
                db_state.local_storage = state.local_storage
                db_state.session_storage = state.session_storage
                db_state.updated_at = datetime.now()
            else:
                # 创建新记录
                db_state = DBBrowserState(
                    site_id=site_id,
                    cookies=state.cookies,
                    local_storage=state.local_storage,
                    session_storage=state.session_storage
                )
                self.session.add(db_state)
                
            await self.session.commit()
            await self.session.refresh(db_state)
            
            self.logger.info(f"浏览器状态已保存: {site_id}")
            return db_state
            
        except Exception as e:
            self.logger.error(f"保存浏览器状态失败: {str(e)}")
            await self.session.rollback()
            return None
            
    async def get_state(self, site_id: str) -> Optional[BrowserState]:
        """获取浏览器状态"""
        try:
            stmt = select(DBBrowserState).where(DBBrowserState.site_id == site_id)
            result = await self.session.execute(stmt)
            db_state = result.scalar_one_or_none()
            
            if not db_state:
                self.logger.debug(f"未找到站点的浏览器状态: {site_id}")
                return None
                
            # 转换为schema模型
            state = BrowserState(
                site_id=db_state.site_id,
                cookies=db_state.cookies,
                local_storage=db_state.local_storage,
                session_storage=db_state.session_storage,
                updated_at=db_state.updated_at
            )
            
            # 验证状态数据
            is_valid, error_msg = state.validate_state()
            if not is_valid:
                self.logger.error(f"数据库中的浏览器状态无效: {error_msg}")
                return None
                
            return state
            
        except Exception as e:
            self.logger.error(f"获取浏览器状态失败: {str(e)}")
            return None
            
    async def delete_state(self, site_id: str) -> bool:
        """删除浏览器状态"""
        try:
            stmt = select(DBBrowserState).where(DBBrowserState.site_id == site_id)
            result = await self.session.execute(stmt)
            db_state = result.scalar_one_or_none()
            
            if db_state:
                await self.session.delete(db_state)
                await self.session.commit()
                self.logger.info(f"浏览器状态已删除: {site_id}")
                return True
            else:
                self.logger.debug(f"未找到要删除的浏览器状态: {site_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除浏览器状态失败: {str(e)}")
            await self.session.rollback()
            return False
            
    async def get_all_states(self) -> List[BrowserState]:
        """获取所有浏览器状态"""
        try:
            stmt = select(DBBrowserState)
            result = await self.session.execute(stmt)
            db_states = result.scalars().all()
            
            states = []
            for db_state in db_states:
                state = BrowserState(
                    site_id=db_state.site_id,
                    cookies=db_state.cookies,
                    local_storage=db_state.local_storage,
                    session_storage=db_state.session_storage
                )
                
                # 验证状态数据
                is_valid, _ = state.validate_state()
                if is_valid:
                    states.append(state)
                    
            return states
            
        except Exception as e:
            self.logger.error(f"获取所有浏览器状态失败: {str(e)}")
            return []


# 全局实例
browserstate_manager = BrowserStateManager()