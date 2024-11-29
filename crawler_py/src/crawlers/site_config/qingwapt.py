from typing import Dict, Any, ClassVar
from .base import BaseSiteConfig

class QingwaPTConfig(BaseSiteConfig):
    """QingwaPT站点配置"""
    
    # 类级别的配置缓存
    _config: ClassVar[Dict[str, Any]] = None
    
    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """获取站点配置，使用缓存避免重复创建"""
        if cls._config is None:
            cls._config = {
                'site_id': 'qingwapt',
                'site_url': 'https://www.qingwapt.com',
                'login_config': {
                    'login_url': 'https://www.qingwapt.com/login.php',
                    'form_selector': '@action=takelogin.php',
                    'pre_login': {
                        'actions': [
                            {
                                'type': 'click',
                                'selector': '#login',
                                'wait_time': 3  # 点击后等待3秒让表单出现
                            }
                        ]
                    },
                    'fields': {
                        'username': {
                            'name': 'username',
                            'type': 'text',
                            'selector': '@name=username',
                            'required': True
                        },
                        'password': {
                            'name': 'password',
                            'type': 'password',
                            'selector': '@name=password',
                            'required': True
                        },
                        'submit': {
                            'name': 'submit',
                            'type': 'submit',
                            'selector': '@value=登录',
                        }
                    },
                    'captcha': {
                        'type': 'background',
                        'element': {
                            'selector': '#captcha',
                            'type': 'background-image',
                            'url_pattern': r'url\("([^"]+)"\)'
                        },
                        'input': {
                            'name': 'imagestring',
                            'type': 'text',
                            'selector': '#captcha-text',
                            'required': True
                        },
                    },
                    'success_check': {
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
                        'selector': '@text()=蝌蚪',
                        'location': 'next',
                        'second_selector': '',
                        'type': 'text'
                    },
                    {
                        'name': 'seeding_score',
                        'selector': '@text()=做种积分',
                        'location': 'next',
                        'second_selector': '',
                        'type': 'text'
                    },
                ]
            }
            
            # 验证配置
            if not cls.validate_config(cls._config):
                raise ValueError(f"站点 {cls._config['site_id']} 的配置无效")
                
        return cls._config 