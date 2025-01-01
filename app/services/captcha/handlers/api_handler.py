import base64
from typing import Optional
from services.managers.setting_manager import SettingManager
from core.logger import get_logger
from twocaptcha import TwoCaptcha
from ..base_handler import BaseCaptchaHandler


class APIHandler(BaseCaptchaHandler):
    """API验证码处理器, 使用2captcha服务"""
    
    def __init__(self, storage_dir: str):
        super().__init__(storage_dir)
        self.logger = get_logger(name=__name__, site_id="api_captcha")
        self.settings_manager = SettingManager.get_instance()
        
        # 初始化配置会在第一次使用时进行
        self.solver = None
        self.timeout = None
        self.polling_interval = None
        self.max_retries = None
        
    async def _init_config(self):
        """初始化2captcha配置"""
        try:
            # 从 SettingManager 获取配置
            api_key = await self.settings_manager.get_setting('captcha_api_key')
            if not api_key:
                raise ValueError("未配置CAPTCHA_API_KEY")
            
            self.timeout = await self.settings_manager.get_setting('captcha_timeout') or 120
            self.polling_interval = await self.settings_manager.get_setting('captcha_poll_interval') or 5.0
            self.max_retries = await self.settings_manager.get_setting('captcha_max_retries') or 3
            
            # 初始化2captcha客户端
            self.solver = TwoCaptcha(api_key)
            self.logger.debug("2captcha客户端初始化成功")
            
        except Exception as e:
            self.logger.error(f"初始化2captcha配置失败: {str(e)}")
            raise
    
    async def handle(self, image_data: bytes, site_id: str) -> Optional[str]:
        """处理验证码
        
        Args:
            image_data: 验证码图片的二进制数据
            site_id: 站点ID
            
        Returns:
            Optional[str]: 识别出的验证码文本，失败返回None
        """
        try:
            # 确保配置已初始化
            if not self.solver:
                await self._init_config()
            
            # 确保图片格式正确
            image_data = self._convert_to_png(image_data)
            
            # 保存原始验证码图片
            image_path = self._save_captcha_image(image_data, site_id)
            
            # 准备API请求参数
            # params = {
            #     'numeric': 6,  # 假设是6位数字验证码
            #     'min_len': 4,
            #     'max_len': 8,
            #     'language': 0,  # 0 = 任何语言
            # }
            
            # 将图片数据转换为base64字符串
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # 发送识别请求
            self.logger.debug("发送验证码识别请求到2captcha")
            result = self.solver.normal(
                image_base64,
                timeout=self.timeout,
                pollingInterval=self.polling_interval
            )
            
            if not result or not result.get('code'):
                self.logger.warning("API返回结果为空")
                return None
                
            captcha_text = result['code']
            self.logger.info(f"API识别结果: {captcha_text}")
            
            # 保存成功识别的验证码图片
            # self._save_captcha_image(image_data, site_id, captcha_text)
            
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