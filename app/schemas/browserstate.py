from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from datetime import datetime


class BrowserState(BaseModel):
    """浏览器状态"""
    site_id: str = Field(..., min_length=1, max_length=500)
    cookies: Dict[str, Any] = Field(default_factory=dict)
    local_storage: Dict[str, str] = {}
    session_storage: Dict[str, str] = {}
    updated_at: Optional[datetime] = None

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
            
            return True, ""
            
        except Exception as e:
            return False, f"验证状态时发生错误: {str(e)}"
