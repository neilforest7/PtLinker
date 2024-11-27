from typing import Optional
from pathlib import Path
from datetime import datetime
from ..base_handler import BaseCaptchaHandler

class ManualHandler(BaseCaptchaHandler):
    """手动验证码处理器"""
    
    async def handle(self, image_data: bytes, site_id: str) -> Optional[str]:
        """手动输入验证码"""
        try:
            # 保存验证码图片
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            image_path = self.storage_dir / f'{site_id}_{timestamp}.png'
            image_path.write_bytes(image_data)

            print(f"请查看验证码图片: {image_path}")
            return input("请输入验证码: ").strip()
        except Exception as e:
            print(f"手动验证码处理失败: {str(e)}")
            return None

    def cleanup(self):
        """清理资源"""
        # 手动处理器不需要特别的清理操作
        pass 