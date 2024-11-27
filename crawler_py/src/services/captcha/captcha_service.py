import os
import json
from typing import Optional, Dict, Type, Union
from pathlib import Path
from loguru import logger
from PIL import Image
import io
import base64
from DrissionPage.items import ChromiumElement

from .base_handler import BaseCaptchaHandler
from .handlers.ocr_handler import OCRHandler
from .handlers.api_handler import APIHandler
from .handlers.manual_handler import ManualHandler
from .handlers.skip_handler import SkipHandler

class CaptchaService:
    """验证码服务"""
    
    HANDLERS: Dict[str, Type[BaseCaptchaHandler]] = {
        'ocr': OCRHandler,
        'api': APIHandler,
        'manual': ManualHandler,
        'skip': SkipHandler
    }

    def __init__(self, storage_dir: str = 'storage/captcha'):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger.bind(service="captcha")
        
        # 获取默认处理方式
        self.default_method = os.getenv('CAPTCHA_DEFAULT_METHOD', 'api')
        
        # 获取站点特定的处理方式
        self.site_methods = {}
        site_methods_str = os.getenv('CAPTCHA_SITE_METHODS', '{}')
        try:
            self.site_methods = json.loads(site_methods_str)
            self.logger.info(f"已加载站点验证码处理方式配置: {self.site_methods}")
        except json.JSONDecodeError as e:
            self.logger.error(f"解析站点验证码处理方式配置失败: {str(e)}")
        
        # 初始化处理器缓存
        self.handler_cache = {}

    def _get_handler(self, site_id: str) -> BaseCaptchaHandler:
        """获取指定站点的验证码处理器"""
        # 如果处理器已经在缓存中，直接返回
        if site_id in self.handler_cache:
            return self.handler_cache[site_id]
            
        # 获取站点的处理方式
        method = self.site_methods.get(site_id, self.default_method)
        self.logger.info(f"站点 {site_id} 使用验证码处理方式: {method}")
        
        # 验证处理方式是否有效
        if method not in self.HANDLERS:
            self.logger.warning(f"无效的验证码处理方式: {method}，使用默认方式: {self.default_method}")
            method = self.default_method
        
        # 创建处理器
        handler_class = self.HANDLERS[method]
        handler = handler_class(self.storage_dir)
        
        # 缓存处理器
        self.handler_cache[site_id] = handler
        return handler

    def _get_image_data(self, element: ChromiumElement) -> Optional[bytes]:
        """从元素获取图片数据"""
        try:
            # 使用src()方法获取图片数据
            image_data = element.src()
            if image_data is None:
                self.logger.warning("无法获取图片数据")
                return None
                
            # 如果返回的是字符串（URL），尝试获取截图
            if isinstance(image_data, str):
                self.logger.debug("获取到URL，尝试获取截图")
                return element.get_screenshot()
                
            return image_data
            
        except Exception as e:
            self.logger.error(f"获取验证码图片数据失败: {str(e)}")
            return None

    def _process_image_data(self, image_data: bytes) -> bytes:
        """处理图片数据，确保格式正确"""
        try:
            # 尝试打开图片
            image = Image.open(io.BytesIO(image_data))
            
            # 如果不是PNG格式，转换为PNG
            if image.format != 'PNG':
                output = io.BytesIO()
                image.save(output, format='PNG')
                return output.getvalue()
            
            return image_data
            
        except Exception as e:
            self.logger.error(f"处理图片数据失败: {str(e)}")
            return image_data

    async def handle_captcha(self, element_or_data: Union[ChromiumElement, bytes], site_id: str) -> Optional[str]:
        """处理验证码
        
        Args:
            element_or_data: 验证码元素或图片数据
            site_id: 站点ID
            
        Returns:
            Optional[str]: 识别出的验证码文本，失败返回None
        """
        try:
            # 获取图片数据
            if isinstance(element_or_data, bytes):
                image_data = element_or_data
            else:
                image_data = self._get_image_data(element_or_data)
                if not image_data:
                    raise Exception("无法获取验证码图片数据")
            
            # 处理图片数据
            image_data = self._process_image_data(image_data)
            
            # 获取处理器并处理验证码
            handler = self._get_handler(site_id)
            return await handler.handle(image_data, site_id)
            
        except Exception as e:
            self.logger.error(f"处理验证码时出错: {str(e)}")
            return None

    def cleanup(self):
        """清理资源"""
        for handler in self.handler_cache.values():
            try:
                handler.cleanup()
            except Exception as e:
                self.logger.error(f"清理验证码处理器时出错: {str(e)}")
        self.handler_cache.clear()