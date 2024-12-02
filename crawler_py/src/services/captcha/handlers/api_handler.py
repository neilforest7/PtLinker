import os
from typing import Optional
import base64
import io
from twocaptcha import TwoCaptcha

from utils.logger import get_logger, setup_logger

from ..base_handler import BaseCaptchaHandler

class APIHandler(BaseCaptchaHandler):
    """API验证码处理器，使用2captcha服务"""
    
    def __init__(self, storage_dir: str):
        super().__init__(storage_dir)
        setup_logger()
        self.logger = get_logger(name=__name__, site_id="api")
        
        # 初始化2captcha客户端
        api_key = os.getenv('CAPTCHA_API_KEY')
        if not api_key:
            raise ValueError("未设置CAPTCHA_API_KEY环境变量")
            
        self.solver = TwoCaptcha(api_key)
        
        # 配置参数
        self.timeout = int(os.getenv('CAPTCHA_TIMEOUT', '120'))
        self.polling_interval = float(os.getenv('CAPTCHA_POLL_INTERVAL', '5.0'))
        self.max_retries = int(os.getenv('CAPTCHA_MAX_RETRIES', '3'))
    
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
            
            # 保存原始验证码图片
            image_path = self._save_captcha_image(image_data, site_id)
            
            # 准备API请求参数
            params = {
                'numeric': 6,  # 假设是6位数字验证码
                'min_len': 4,
                'max_len': 8,
                'language': 0,  # 0 = 任何语言
            }
            
            # 将图片数据转换为base64字符串
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # 发送识别请求
            self.logger.debug("发送验证码识别请求到2captcha")
            result = self.solver.normal(
                image_base64,
                **params,
                timeout=self.timeout,
                pollingInterval=self.polling_interval
            )
            
            if not result or not result.get('code'):
                self.logger.warning("API返回结果为空")
                return None
                
            captcha_text = result['code']
            self.logger.info(f"API识别结果: {captcha_text}")
            
            # 保存成功识别的验证码图片
            self._save_captcha_image(image_data, site_id, captcha_text)
            
            return captcha_text
            
        except Exception as e:
            self.logger.error(f"API识别验证码失败: {str(e)}")
            # 保存失败的验证码图片以供分析
            self._save_captcha_image(image_data, site_id)
            return None
    
    def cleanup(self):
        """清理资源"""
        try:
            self.solver = None
        except Exception as e:
            self.logger.error(f"清理API资源失败: {str(e)}")
        finally:
            self.solver = None