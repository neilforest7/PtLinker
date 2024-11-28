from typing import Optional
from loguru import logger

from ..base_handler import BaseCaptchaHandler

class SkipHandler(BaseCaptchaHandler):
    """跳过验证码处理器，用于不需要验证码的情况"""
    
    def __init__(self, storage_dir: str):
        super().__init__(storage_dir)
        self.logger = logger.bind(handler="skip", site_id="SkipHandler")
    
    async def handle(self, image_data: bytes, site_id: str) -> Optional[str]:
        """处理验证码
        
        Args:
            image_data: 验证码图片的二进制数据
            site_id: 站点ID
            
        Returns:
            Optional[str]: 始终返回None
        """
        self.logger.info(f"跳过站点 {site_id} 的验证码处理")
        
        # 保存验证码图片以供分析
        self._save_captcha_image(image_data, site_id)
        
        return None
    
    def cleanup(self):
        """清理资源"""
        # 跳过处理器不需要特别的清理操作
        pass 