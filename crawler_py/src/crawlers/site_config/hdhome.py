from typing import Dict, Any, ClassVar
from .base import BaseSiteConfig

class HDHomeConfig(BaseSiteConfig):
    """HDHome站点配置"""
    
    # 类级别的配置缓存
    _config: ClassVar[Dict[str, Any]] = None
    
    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """获取站点配置，使用缓存避免重复创建"""
        if cls._config is None:
            cls._config = {
                'site_id': 'hdhome',
                'site_url': 'https://hdhome.org',
                'login_config': {
                    'login_url': 'https://hdhome.org/login.php',
                    'form_selector': '@action=takelogin.php',
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
                        'ssl': {
                            'name': 'ssl',
                            'type': 'checkbox',
                            'selector': '@name=ssl',
                            'value': 'on'
                        },
                        'trackerssl': {
                            'name': 'trackerssl',
                            'type': 'checkbox',
                            'selector': '@name=trackerssl',
                            'value': 'on'
                        },
                        'submit': {
                            'name': 'submit',
                            'selector': '@type=submit',
                        }
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
                        'selector': '@text()=魔力值',
                        'location': 'next',
                        'second_selector': '',
                        'type': 'text',
                    },
                    {
                        'name': 'seeding_score',
                        'selector': '@text()=做种积分',
                        'location': 'next',
                        'second_selector': '',
                        'type': 'text'
                    },
                    {
                        'name': 'hr_count',
                        'selector': '@title=查看HR详情',
                        'type': 'text'
                    },
                ],
                'checkin_config': 
                    {
                        'checkin_url': 'https://hdhome.org/attendance.php',
                        'checkin_button': {
                            'name': 'checkin_button',
                            'selector': '@href$attendance.php',
                        },
                        'success_check': {
                            'element':{
                                'name': 'checkin_result',
                                'selector': '@tag()=h2',
                                'type': 'text'
                            },
                            'sign':{
                                'success': '签到成功',
                                'already': '今天已经签到过了',
                                'error': '签到失败',
                            }
                        }
                    }
            }
            
            # 验证配置
            if not cls.validate_config(cls._config):
                raise ValueError(f"站点 {cls._config['site_id']} 的配置无效")
                
        return cls._config 