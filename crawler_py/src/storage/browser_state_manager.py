from datetime import datetime
from typing import Any, Dict, Optional

from models.storage import BrowserState, LoginState
from utils.logger import get_logger


class BrowserStateManager:
    """浏览器状态管理器
    
    负责管理浏览器的完整状态，包括：
    - cookies
    - local_storage
    - session_storage
    - login_state
    
    同时提供专门的cookie管理功能
    """
    
    def __init__(self, storage_manager):
        """
        Args:
            storage_manager: StorageManager实例
        """
        self.storage_manager = storage_manager
        self.logger = get_logger(__name__, site_id='BrwsStat')
        
    async def save_state(self, site_id: str, browser_state: BrowserState) -> bool:
        """保存完整的浏览器状态
        
        Args:
            site_id: 站点ID
            browser_state: 浏览器状态对象
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 验证状态
            is_valid, error_msg = browser_state.validate_state()
            if not is_valid:
                self.logger.error(f"浏览器状态验证失败: {error_msg}")
                return False
            
            # 更新登录状态的时间戳
            if browser_state.login_state.is_logged_in:
                browser_state.login_state.last_login_time = int(datetime.now().timestamp())
            
            # 通过storage_manager保存状态
            browser_state_path = self.storage_manager.paths.get_browser_state_path(site_id)
            await self.storage_manager.storage.save(
                browser_state.model_dump(),
                self.storage_manager.paths.get_relative_path(browser_state_path)
            )
            self.logger.debug(f"已保存站点 {site_id} 的浏览器状态")
            return True
            
        except Exception as e:
            self.logger.error(f"保存站点 {site_id} 的浏览器状态失败: {str(e)}")
            return False
    
    async def restore_state(self, site_id: str) -> Optional[BrowserState]:
        """恢复完整的浏览器状态
        
        Args:
            site_id: 站点ID
            
        Returns:
            Optional[BrowserState]: 恢复的浏览器状态，如果不存在则返回None
        """
        try:
            # 获取浏览器状态文件路径
            browser_state_path = self.storage_manager.paths.get_browser_state_path(site_id)
            relative_path = self.storage_manager.paths.get_relative_path(browser_state_path)
            
            # 检查文件是否存在
            if not await self.storage_manager.storage.exists(relative_path):
                self.logger.debug(f"站点 {site_id} 的浏览器状态文件不存在")
                return None
            
            # 加载状态数据
            try:
                state_data = await self.storage_manager.storage.load(relative_path)
            except Exception as e:
                self.logger.error(f"加载站点 {site_id} 的浏览器状态文件失败: {str(e)}")
                return None
            
            if not state_data:
                self.logger.debug(f"站点 {site_id} 的浏览器状态为空")
                return None
            
            try:
                # 转换为BrowserState对象
                browser_state = BrowserState(**state_data)
                
                # 验证状态
                is_valid, error_msg = browser_state.validate_state()
                if not is_valid:
                    self.logger.error(f"{site_id} 恢复的浏览器状态验证失败: {error_msg}")
                    return None
                
                self.logger.debug(f"已恢复站点 {site_id} 的浏览器状态，包含 {len(browser_state.cookies)} 个cookies")
                return browser_state
                
            except Exception as e:
                self.logger.error(f"解析站点 {site_id} 的浏览器状态数据失败: {str(e)}")
                return None
            
        except Exception as e:
            self.logger.error(f"恢复站点 {site_id} 的浏览器状态失败: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)
            return None
    
    async def _batch_update_state(self, site_id: str, 
                                cookies: Optional[Dict[str, Any]] = None,
                                local_storage: Optional[Dict[str, str]] = None,
                                session_storage: Optional[Dict[str, str]] = None,
                                login_state: Optional[LoginState] = None) -> bool:
        """批量更新浏览器状态
        
        Args:
            site_id: 站点ID
            cookies: 要更新的cookies
            local_storage: 要更新的local storage
            session_storage: 要更新的session storage
            login_state: 要更新的登录状态
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 获取当前状态
            browser_state = await self.restore_state(site_id)
            if not browser_state:
                browser_state = BrowserState()
            
            # 更新各个部分
            if cookies is not None:
                browser_state.cookies.update(cookies)
                
            if local_storage is not None:
                browser_state.local_storage.update(local_storage)
                
            if session_storage is not None:
                browser_state.session_storage.update(session_storage)
                
            if login_state is not None:
                browser_state.login_state = login_state
            
            # 保存更新后的状态
            return await self.save_state(site_id, browser_state)
            
        except Exception as e:
            self.logger.error(f"批量更新站点 {site_id} 的浏览器状态失败: {str(e)}")
            return False
            
    async def update_cookies(self, site_id: str, new_cookies: Dict[str, Any]) -> bool:
        """更新站点的cookies
        
        Args:
            site_id: 站点ID
            new_cookies: 新的cookies
            
        Returns:
            bool: 更新是否成功
        """
        return await self._batch_update_state(site_id, cookies=new_cookies)
    
    async def update_local_storage(self, site_id: str, new_local_storage: Dict[str, Any]) -> bool:
        """更新local storage中的值
        
        Args:
            site_id: 站点ID
            new_local_storage: 新的local storage
            
        Returns:
            bool: 更新是否成功
        """
        return await self._batch_update_state(site_id, local_storage=new_local_storage)
    
    async def update_session_storage(self, site_id: str, new_session_storage: Dict[str, Any]) -> bool:
        """更新session storage中的值
        
        Args:
            site_id: 站点ID
            new_session_storage: 新的session storage
            
        Returns:
            bool: 更新是否成功
        """
        return await self._batch_update_state(site_id, session_storage=new_session_storage)
    
    async def update_login_state(self, site_id: str, 
                                is_logged_in: bool, 
                                username: Optional[str] = None, 
                                last_login_time: Optional[str] = None) -> bool:
        """更新登录状态
        
        Args:
            site_id: 站点ID
            is_logged_in: 是否已登录
            username: 用户名
            
        Returns:
            bool: 更新是否成功
        """
        login_state = LoginState(is_logged_in=is_logged_in, username=username, last_login_time=last_login_time)
        return await self._batch_update_state(site_id, login_state=login_state)
    
    async def clear_state(self, site_id: str) -> bool:
        """清除站点的浏览器状态
        
        Args:
            site_id: 站点ID
            
        Returns:
            bool: 清除是否成功
        """
        try:
            # 创建一个新的空状态并保存
            browser_state = BrowserState()
            return await self.save_state(site_id, browser_state)
            
        except Exception as e:
            self.logger.error(f"清除站点 {site_id} 的浏览器状态失败: {str(e)}")
            return False 