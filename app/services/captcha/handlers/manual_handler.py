import os
import time
import webbrowser
from pathlib import Path
from typing import Optional

from core.logger import get_logger, setup_logger

from ..base_handler import BaseCaptchaHandler


class ManualHandler(BaseCaptchaHandler):
    """手动验证码处理器，打开图片让用户手动输入"""
    
    def __init__(self, storage_dir: str):
        super().__init__(storage_dir)
        # setup_logger()
        self.logger = get_logger(name=__name__, site_id="manualcap")
        self.timeout = int(os.getenv('MANUAL_CAPTCHA_TIMEOUT', '300'))  # 5分钟超时
    
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
            
            # 保存验证码图片
            image_path = self._save_captcha_image(image_data, site_id)
            
            # 打开图片
            self.logger.info(f"正在打开验证码图片: {image_path}")
            webbrowser.open(str(image_path))
            
            # 等待用户输入
            self.logger.info("请查看打开的验证码图片，并在下面输入验证码:")
            start_time = time.time()
            
            while True:
                if time.time() - start_time > self.timeout:
                    self.logger.error("等待输入超时")
                    return None
                
                try:
                    captcha_text = input("请输入验证码 (输入q退出): ").strip()
                    if captcha_text.lower() == 'q':
                        self.logger.info("用户取消输入")
                        return None
                    
                    if captcha_text:
                        self.logger.info(f"收到验证码输入: {captcha_text}")
                        # 保存成功识别的验证码图片
                        self._save_captcha_image(image_data, site_id, captcha_text)
                        return captcha_text
                    
                    self.logger.warning("验证码不能为空，请重新输入")
                    
                except KeyboardInterrupt:
                    self.logger.info("用户中断输入")
                    return None
                except Exception as e:
                    self.logger.error(f"输入过程出错: {str(e)}")
                    return None
            
        except Exception as e:
            self.logger.error(f"手动处理验证码失败: {str(e)}")
            # 保存失败的验证码图片以供分析
            self._save_captcha_image(image_data, site_id)
            return None
    
    def cleanup(self):
        """清理资源"""
        # 手动处理器不需要特别的清理操作
        pass 