from typing import Optional
from pathlib import Path
from ..base_handler import BaseCaptchaHandler

class SkipHandler(BaseCaptchaHandler):
    """跳过验证码处理器"""
    
    async def handle(self, image_data: bytes, site_id: str) -> Optional[str]:
        """跳过验证码处理"""
        return None

    def cleanup(self):
        """清理资源"""
        # 跳过处理器不需要特别的清理操作
        pass 