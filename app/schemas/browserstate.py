from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from datetime import datetime


class BrowserState(BaseModel):
    """浏览器状态"""
    site_id: str = Field(..., min_length=1, max_length=500)
    cookies: Dict[str, Any] = Field(default_factory=dict)
    local_storage: Dict[str, str] = {}
    session_storage: Dict[str, str] = {}

    def validate_state(self) -> Tuple[bool, str]:
        """验证状态数据的有效性
        
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        try:
            # 1. 验证cookies格式
            for name, cookie in self.cookies.items():
                if not isinstance(name, str):
                    return False, f"Cookie名称必须是字符串，而不是 {type(name)}"
                if isinstance(cookie, dict):
                    required_fields = {'value', 'domain', 'path'}
                    missing_fields = required_fields - set(cookie.keys())
                    if missing_fields:
                        return False, f"Cookie {name} 缺少必要字段: {missing_fields}"
                elif not isinstance(cookie, str):
                    return False, f"Cookie {name} 的值必须是字符串或字典，而不是 {type(cookie)}"
            
            # 2. 验证storage格式
            for key, value in self.local_storage.items():
                if not isinstance(key, str):
                    return False, f"localStorage键必须是字符串，而不是 {type(key)}"
                if not isinstance(value, str):
                    return False, f"localStorage值必须是字符串，而不是 {type(value)}"
                    
            for key, value in self.session_storage.items():
                if not isinstance(key, str):
                    return False, f"sessionStorage键必须是字符串，而不是 {type(key)}"
                if not isinstance(value, str):
                    return False, f"sessionStorage值必须是字符串，而不是 {type(value)}"
            
            # 3. 验证登录状态的一致性
            if self.login_state.is_logged_in:
                if not self.login_state.username:
                    return False, "登录状态为已登录但缺少用户名"
                if not self.login_state.last_login_time:
                    return False, "登录状态为已登录但缺少登录时间"
            else:
                if self.login_state.username or self.login_state.last_login_time:
                    return False, "登录状态为未登录但存在用户名或登录时间"
            
            # 4. 验证时间戳的有效性
            if self.login_state.last_login_time:
                current_time = int(datetime.now().timestamp())
                if self.login_state.last_login_time > current_time:
                    return False, "登录时间戳无效（未来时间）"
                if current_time - self.login_state.last_login_time > 90 * 24 * 3600:  # 90天
                    return False, "登录时间戳过期（超过90天）"
            
            return True, ""
            
        except Exception as e:
            return False, f"验证状态时发生错误: {str(e)}"
