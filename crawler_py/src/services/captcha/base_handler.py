from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path
import os
from datetime import datetime
from PIL import Image
import io

class BaseCaptchaHandler(ABC):
    """验证码处理器基类"""
    
    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _save_captcha_image(self, image_data: bytes, site_id: str, result: Optional[str] = None) -> str:
        """保存验证码图片
        
        Args:
            image_data: 图片二进制数据
            site_id: 站点ID
            result: 识别结果
            
        Returns:
            str: 保存的文件路径
        """
        # 创建站点目录
        site_dir = self.storage_dir / site_id
        site_dir.mkdir(exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_str = f"_{result}" if result else ""
        filename = f"captcha_{timestamp}{result_str}.png"
        
        # 保存图片
        file_path = site_dir / filename
        with open(file_path, 'wb') as f:
            f.write(image_data)
            
        return str(file_path)
    
    def _get_image_format(self, image_data: bytes) -> str:
        """获取图片格式"""
        try:
            image = Image.open(io.BytesIO(image_data))
            return image.format or 'PNG'
        except Exception:
            return 'PNG'
    
    def _convert_to_png(self, image_data: bytes) -> bytes:
        """将图片转换为PNG格式"""
        try:
            image = Image.open(io.BytesIO(image_data))
            if image.format != 'PNG':
                output = io.BytesIO()
                image.save(output, format='PNG')
                return output.getvalue()
        except Exception:
            pass
        return image_data
    
    @abstractmethod
    async def handle(self, image_data: bytes, site_id: str) -> Optional[str]:
        """处理验证码
        
        Args:
            image_data: 验证码图片的二进制数据
            site_id: 站点ID
            
        Returns:
            Optional[str]: 识别出的验证码文本，失败返回None
        """
        pass
    
    def cleanup(self):
        """清理资源，子类可以重写此方法以实现自定义清理逻辑"""
        pass 