from typing import Optional
from pathlib import Path
from datetime import datetime
import ddddocr
from ..base_handler import BaseCaptchaHandler
from loguru import logger

class OCRHandler(BaseCaptchaHandler):
    """OCR验证码处理器，使用ddddocr进行本地识别"""
    
    def __init__(self, storage_dir: str):
        super().__init__(storage_dir)
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.logger = logger.bind(handler="ocr")
    
    async def handle(self, image_data: bytes, site_id: str) -> Optional[str]:
        """处理验证码
        
        Args:
            image_data: 验证码图片的二进制数据
            site_id: 站点ID
            
        Returns:
            Optional[str]: 识别出的验证码文本，失败返回None
        """
        try:
            # 确保图片格式正确
            image_data = self._convert_to_png(image_data)
            
            # 识别验证码
            self.logger.debug("开始OCR识别验证码")
            result = self.ocr.classification(image_data)
            
            if not result:
                self.logger.warning("OCR识别结果为空")
                # 保存失败的验证码图片以供分析
                self._save_captcha_image(image_data, site_id)
                return None
                
            self.logger.info(f"OCR识别结果: {result}")
            
            # 保存成功识别的验证码图片
            self._save_captcha_image(image_data, site_id, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"OCR识别验证码失败: {str(e)}")
            # 保存失败的验证码图片以供分析
            self._save_captcha_image(image_data, site_id)
            return None
    
    def cleanup(self):
        """清理资源"""
        try:
            del self.ocr
        except Exception as e:
            self.logger.error(f"清理OCR资源失败: {str(e)}")
        finally:
            self.ocr = None 