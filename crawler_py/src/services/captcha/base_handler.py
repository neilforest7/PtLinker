from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path

class BaseCaptchaHandler(ABC):
    """验证码处理基础接口"""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    async def handle(self, image_data: bytes, site_id: str) -> Optional[str]:
        """处理验证码"""
        pass

    @abstractmethod
    def cleanup(self):
        """清理资源"""
        pass 