from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from models.crawler import (CheckInConfig, CrawlerTaskConfig, ExtractRuleSet,
                            LoginConfig, WebElement)
from handlers.credentials import CredentialsManager


@dataclass
class BaseSiteConfig:
    """站点基础配置类"""
    site_id: str
    site_url: str
    login_config: Dict[str, Any]
    extract_rules: Dict[str, Any]
    checkin_config: Dict[str, Any]
    _credentials_manager = CredentialsManager()

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """
        获取站点配置
        Returns:
            Dict[str, Any]: 包含站点配置的字典
        """
        raise NotImplementedError("子类必须实现get_config方法")
    
    @classmethod
    def create_task_config(
        cls,
        username: Optional[str] = None,
        password: Optional[str] = None,
        task_id: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> CrawlerTaskConfig:
        """创建任务配置"""
        # 获取站点基础配置
        config = cls.get_config()
        
        # 获取站点凭证(优先使用特定凭证,其次使用环境变量凭证)
        site_credential = cls._credentials_manager.get_site_credential(config['site_id'])
        if site_credential:
            # 将凭证信息添加到配置中
            config['credentials'] = site_credential
            username = site_credential.username
            password = site_credential.password
        
        # 生成任务ID
        if task_id is None:
            task_id = f"{config['site_id']}-{int(datetime.now().timestamp())}"
        
        # 转换登录配置，注入用户名和密码
        if config.get('login_config'):
            login_config_dict = config['login_config'].copy()
            
            # 注入用户名和密码到表单字段
            if 'fields' in login_config_dict:
                fields_dict = login_config_dict['fields'].copy()
                
                if 'username' in fields_dict and username:
                    fields_dict['username'] = {
                        **fields_dict['username'],
                        'value': username
                    }
                
                if 'password' in fields_dict and password:
                    fields_dict['password'] = {
                        **fields_dict['password'],
                        'value': password
                    }
                
                login_config_dict['fields'] = fields_dict
            
            login_config = LoginConfig(**login_config_dict)
        else:
            login_config = None
        
        # 转换提取规则
        if config.get('extract_rules'):
            extract_rules = ExtractRuleSet(rules=[WebElement(**rule) for rule in config['extract_rules']])
        else:
            extract_rules = None
        
        # 转换签到配置
        if config.get('checkin_config'):
            checkin_config_dict = config['checkin_config'].copy()
            checkin_config = CheckInConfig(**checkin_config_dict)
        else:
            checkin_config = None
        
        # 创建任务配置
        task_config = CrawlerTaskConfig(
            task_id=task_id,
            site_id=config['site_id'],
            site_url=[config['site_url']],  # 转换为列表格式
            credentials=config.get('credentials'),  # 添加凭证信息
            login_config=login_config,
            extract_rules=extract_rules,
            checkin_config=checkin_config,
            custom_config=custom_config or {}
        )
        
        return task_config
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> bool:
        """
        验证配置是否有效
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 配置是否有效
        """
        required_fields = ['site_id', 'site_url']
        return all(field in config for field in required_fields) 