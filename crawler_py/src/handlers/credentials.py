import json
import os
from pathlib import Path
from typing import Dict, Optional

from models.crawler import SiteCredential
from utils.logger import get_logger


class CredentialsManager:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.credentials_file = Path(os.getenv('CREDENTIALS_PATH', 'config/credentials.json'))
        self._credentials: Dict = {}
        self._load_credentials()
    
    def _load_credentials(self):
        """加载凭证配置"""
        try:
            if self.credentials_file.exists():
                self._credentials = json.loads(self.credentials_file.read_text(encoding='utf-8'))
                self.logger.info(f"成功加载凭证配置文件: {self.credentials_file}")
            else:
                self.logger.warning(f"凭证配置文件不存在: {self.credentials_file}，将仅使用环境变量凭证")
                self._credentials = {}
        except Exception as e:
            self.logger.error(f"加载凭证配置失败: {str(e)}")
            self._credentials = {}
    
    def get_site_credential(self, site_id: str) -> Optional[SiteCredential]:
        """获取指定站点的凭证,优先使用站点特定凭证,其次使用环境变量凭证"""
        try:
            # 1. 尝试获取站点特定凭证
            if site_id in self._credentials:
                site_cred = self._credentials[site_id]
                if site_cred.get('enabled', True):  # 检查凭证是否启用
                    self.logger.debug(f"使用站点 {site_id} 的特定凭证")
                    return SiteCredential(**site_cred)
                else:
                    self.logger.warning(f"站点 {site_id} 的特定凭证已禁用")
            
            # 2. 尝试使用环境变量凭证
            env_username = os.getenv('LOGIN_USERNAME')
            env_password = os.getenv('LOGIN_PASSWORD')
            if env_username and env_password:
                self.logger.debug(f"站点 {site_id} 使用环境变量凭证")
                return SiteCredential(
                    username=env_username,
                    password=env_password,
                    enabled=True,
                    description="环境变量凭证"
                )
            
            self.logger.warning(f"站点 {site_id} 未找到任何可用凭证")
            return None
            
        except Exception as e:
            self.logger.error(f"获取站点 {site_id} 凭证时出错: {str(e)}")
            return None