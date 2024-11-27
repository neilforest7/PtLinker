from typing import Optional
from pathlib import Path
from datetime import datetime
import ddddocr
from ..base_handler import BaseCaptchaHandler

class OCRHandler(BaseCaptchaHandler):
    """OCR验证码处理器"""
    
    def __init__(self, storage_dir: Path):
        super().__init__(storage_dir)
        self.ocr = ddddocr.DdddOcr(show_ad=False)

    async def handle(self, image_data: bytes, site_id: str) -> Optional[str]:
        """使用OCR识别验证码"""
        try:
            # 保存验证码图片
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            image_path = self.storage_dir / f'{site_id}_{timestamp}.png'
            image_path.write_bytes(image_data)

            # 使用ddddocr识别验证码
            result = self.ocr.classification(image_data)
            return result
        except Exception as e:
            print(f"OCR验证码识别失败: {str(e)}")
            return None

    def cleanup(self):
        """清理资源"""
        # OCR处理器不需要特别的清理操作
        pass 