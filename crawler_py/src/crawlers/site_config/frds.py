from typing import Dict, Any, ClassVar
from .base import BaseSiteConfig

class FrdsConfig(BaseSiteConfig):
    """Frds站点配置"""
    
    # 类级别的配置缓存
    _config: ClassVar[Dict[str, Any]] = None
    
    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """获取站点配置，使用缓存避免重复创建"""
        if cls._config is None:
            cls._config = {
                'site_id': 'frds',
                'site_url': 'https://pt.keepfrds.com',
                'login_config': {
                    'login_url': 'https://pt.keepfrds.com/login.php',
                    'form_selector': '@action=takelogin.php',
                    'pre_login': {
                        'actions': [
                            {
                                'type': 'bypass-cf-turnstile',
                                'selector': '@class=cf-turnstile',
                                'wait_time': 5  # 点击后等待3秒让表单出现
                            }
                        ]
                    },
                    'fields': {
                        'username': {
                            'name': 'username',
                            'selector': '@name=username',
                            'type': 'text',
                            'required': True
                        },
                        'password': {
                            'name': 'password',
                            'selector': '@name=password',
                            'type': 'password',
                            'required': True
                        },
                        'submit': {
                            'name': 'submit',
							'selector': '@value=Boarding'
                        },
                    },
                    'success_check': {
                        'name': 'login_result',
                        'selector': '@class=User_Name',
                        'type': 'text'
                    }
                },
                'extract_rules': [
                    {
                        'name': 'username',
                        'selector': '@class=User_Name',
                        'type': 'text',
                        'required': True
                    },
                    {
                        'name': 'seeding_list',
                        'selector': '@href^javascript: getusertorrentlistajax',
                        'index': 2
                    },
                    {
                        'name': 'seeding_list_container',
                        'selector': '#ka1',
                        'type': 'text',
                        'need_pre_action': True
                    },
                    {
                        'name': 'seeding_list_table',
                        'selector': '@tag()=table',
                        'type': 'text',
                        'need_pre_action': True,
                        'index': 3
                    },
                    {
                        'name': 'seeding_list_pagination',
                        'selector': '@class=nexus-pagination',
                        'type': 'text',
                        'need_pre_action': True
                    },
                    {
                        'name': 'user_class',
                        'selector': '@text()=等级',
                        'location': 'next-child',
                        'second_selector': '@@tag()=img@@alt@@src',
                        'type': 'attribute',
                        'attribute': 'alt',
                    },
                    {
                        'name': 'join_time',
                        'selector': '@text()=加入日期',
                        'location': 'next',
                        'second_selector': '',
                        'type': 'text'
                    },
                    {
                        'name': 'last_active',
                        'selector': '@text()=最近动向',
                        'location': 'next',
                        'second_selector': '',
                        'type': 'text'
                    },
                    {
                        'name': 'upload',
                        'selector': '@text()=上传量',
                        'location': 'parent',
                        'second_selector': '',
                        'type': 'text'
                    },
                    {
                        'name': 'download',
                        'selector': '@text()=下载量',
                        'location': 'parent',
                        'second_selector': '',
                        'type': 'text'
                    },
                    {
                        'name': 'ratio',
                        'selector': '@text()=分享率',
                        'location': 'next',
                        'second_selector': '@tag()=font',
                        'type': 'text'
                    },
                    {
                        'name': 'bonus',
                        'selector': '@@text()=魔力值@@tag()=strong',
                        'location': 'parent',
                        'second_selector': '',
                        'type': 'text',
                    },
                    {
                        'name': 'bonus_per_hour',
                        'selector': '@text()^你当前每小时能获取',
                        'type': 'text',
                        'need_pre_action': True,
                        'pre_action_type': 'goto',
                        'page_url': '/mybonus.php'
                    },
                ],
            }
            
            # 验证配置
            if not cls.validate_config(cls._config):
                raise ValueError(f"站点 {cls._config['site_id']} 的配置无效")
                
        return cls._config 