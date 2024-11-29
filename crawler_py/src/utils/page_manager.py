from typing import Dict, Optional

from config.drission_config import DrissionConfig, default_config
from DrissionPage import Chromium, MixTab, SessionPage
from DrissionPage.errors import PageDisconnectedError
from loguru import logger


class PageManager:
    """DrissionPage管理器"""
    
    def __init__(self, config: DrissionConfig = default_config):
        self.config = config
        self._browser: Optional[Chromium] = None
        self._session_page: Optional[SessionPage] = None
        self._current_tab: Optional[MixTab] = None
    
    @property
    def browser(self) -> Chromium:
        """获取浏览器实例"""
        if self._browser is None:
            self._browser = Chromium(**self.config.browser.model_dump())
            logger.info("Created new browser instance")
        return self._browser
    
    @property
    def current_tab(self) -> MixTab:
        """获取当前标签页"""
        if self._current_tab is None or not self._current_tab.is_alive():
            self._current_tab = self.browser.latest_tab
            if self._current_tab is None:
                self._current_tab = self.browser.new_tab()
            logger.info("Created new browser tab")
        return self._current_tab
    
    @property
    def session_page(self) -> SessionPage:
        """获取请求会话实例"""
        if self._session_page is None:
            self._session_page = SessionPage(**self.config.session.model_dump())
            logger.info("Created new session page instance")
        return self._session_page
    
    def new_tab(self) -> MixTab:
        """创建新标签页"""
        self._current_tab = self.browser.new_tab()
        logger.info("Created new browser tab")
        return self._current_tab
    
    def switch_tab(self, tab_id: str = None, title: str = None, url: str = None) -> MixTab:
        """切换标签页"""
        if tab_id:
            tab = self.browser.get_tab(tab_id=tab_id)
        elif title:
            tab = self.browser.get_tab(title=title)
        elif url:
            tab = self.browser.get_tab(url=url)
        else:
            tab = self.browser.latest_tab
            
        if tab:
            self._current_tab = tab
            self.browser.activate_tab(tab)
            logger.info(f"Switched to tab: {tab.title}")
        return self._current_tab
    
    def close_tab(self, tab: MixTab = None, others: bool = False):
        """关闭标签页"""
        if tab is None:
            tab = self._current_tab
        if tab:
            tab.close(others=others)
            if tab == self._current_tab:
                self._current_tab = None
            logger.info("Tab closed")
    
    def close_browser(self):
        """关闭浏览器"""
        if self._browser:
            try:
                self._browser.quit(del_data=True)
                logger.info("Browser closed")
            except PageDisconnectedError:
                logger.warning("Browser already disconnected")
            finally:
                self._browser = None
                self._current_tab = None
    
    def close_session(self):
        """关闭会话"""
        if self._session_page:
            self._session_page.close()
            self._session_page = None
            logger.info("Session page closed")
    
    def close(self):
        """关闭所有实例"""
        self.close_browser()
        self.close_session()
    
    def set_cookies(self, cookies: Dict):
        """设置cookies"""
        self.browser.set.cookies(cookies)
        logger.success("Cookies set")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close() 