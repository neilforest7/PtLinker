import base64
import os
from typing import Optional, Union

import requests
from DrissionPage.items import ChromiumElement
from core.logger import get_logger
from services.managers.setting_manager import SettingManager

from .handlers.api_handler import APIHandler
from .handlers.ocr_handler import OCRHandler


class CaptchaService:
    def __init__(self):
        self.logger = get_logger(name=__name__, site_id="Captcha")
        self.settings_manager = SettingManager.get_instance()
        
        # 初始化配置会在第一次使用时进行
        self.storage_dir = None
        self.default_method = None
        self.api_handler = None
        self.ocr_handler = None
        
    async def _init_config(self):
        """初始化配置"""
        try:
            # 从 SettingManager 获取配置
            self.storage_dir = await self.settings_manager.get_setting('captcha_storage_path') or 'storage/captcha'
            self.default_method = await self.settings_manager.get_setting('captcha_default_method') or 'api'
            
            # 初始化处理器
            self.api_handler = APIHandler(self.storage_dir)
            self.ocr_handler = OCRHandler(self.storage_dir)
            
            self.logger.info(f"使用验证码处理方式: {self.default_method}")
            
        except Exception as e:
            self.logger.error(f"初始化验证码服务配置失败: {str(e)}")
            raise
            
    async def handle_captcha(self, input_data: Union[ChromiumElement, str, bytes], site_id: str) -> Optional[str]:
        """处理验证码
        
        Args:
            element: 验证码元素，可以是WebElement、URL字符串或bytes数据
            site_id: 站点ID，用于日志记录
            
        Returns:
            str: 识别出的验证码文本，失败返回None
        """
        try:
            # 确保配置已初始化
            if not self.api_handler:
                await self._init_config()
                
            # 获取验证码数据
            captcha_data = await self._get_captcha_data(input_data)
            if not captcha_data:
                return None
                
            # 根据默认处理方式选择处理器
            if self.default_method == 'api':
                return await self.api_handler.handle(captcha_data, site_id)
            else:
                return await self.ocr_handler.handle(captcha_data, site_id)
                
        except Exception as e:
            self.logger.error(f"处理验证码失败: {str(e)}")
            return None
            
    async def _get_captcha_data(self, input_data: Union[ChromiumElement, str, bytes]) -> Optional[bytes]:
        """获取验证码数据
        
        Args:
            element: 验证码元素，可以是WebElement、URL字符串或bytes数据
            
        Returns:
            bytes: 验证码图片的二进制数据
        """
        try:
            if isinstance(input_data, ChromiumElement):
                # 如果是WebElement，获取src属性
                src = input_data.src(base64_to_bytes=True)
                if not src:
                    self.logger.error("验证码元素没有src属性")
                    return None
                    
                # 如果是base64编码的图片
                if src.startswith('data:image'):
                    try:
                        # 提取base64数据部分
                        base64_data = src.split(',')[1]
                        return base64.b64decode(base64_data)
                    except Exception as e:
                        self.logger.error(f"解析base64图片数据失败: {str(e)}")
                        return None
                        
                return await self._download_image(src)
                
            elif isinstance(input_data, str):
                # 如果是URL字符串
                if input_data.startswith('http'):
                    return await self._download_image(input_data)
                # 如果是base64字符串
                elif input_data.startswith('data:image'):
                    try:
                        base64_data = input_data.split(',')[1]
                        return base64.b64decode(base64_data)
                    except Exception as e:
                        self.logger.error(f"解析base64字符串失败: {str(e)}")
                        return None
                else:
                    self.logger.error("无效的字符串格式")
                    return None
                    
            elif isinstance(input_data, bytes):
                # 如果已经是bytes数据，直接返回
                return input_data
                
            else:
                self.logger.error(f"不支持的元素类型: {type(input_data)}")
                return None
                
        except Exception as e:
            self.logger.error(f"获取验证码数据失败: {str(e)}")
            return None
            
    async def _download_image(self, url: str) -> Optional[bytes]:
        """下载图片
        
        Args:
            url: 图片URL
            
        Returns:
            bytes: 图片的二进制数据
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.content
        except Exception as e:
            self.logger.error(f"下载验证码图片失败: {str(e)}")
            return None
            
    def cleanup(self):
        """清理资源"""
        try:
            self.api_handler.cleanup()
            self.ocr_handler.cleanup()
        except Exception as e:
            self.logger.error(f"清理验证码服务资源失败: {str(e)}")