from typing import Dict, Any, ClassVar
from .base import BaseSiteConfig

class U2Config(BaseSiteConfig):
    """U2站点配置"""
    
    # 类级别的配置缓存
    _config: ClassVar[Dict[str, Any]] = None
    
    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """获取站点配置，使用缓存避免重复创建"""
        if cls._config is None:
            cls._config = {
                'site_id': 'u2',
                'site_url': 'https://u2.dmhy.org',
                'login_config': {
                    'login_url': '/portal.php',
                    'form_selector': '@action=takelogin.php',
                    'pre_login': {
                        'actions': [
                            {
                                'type': 'click',
                                'selector': '@alt=CAPTCHA Image',
                                'wait_time': 1  # 点击后等待3秒让验证码出现
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
                            'selector': '@@text()^LINK@@type=button',
                        }
                    },
                    'captcha': {
                        'type': 'custom',
                        'element': {
                            'name': 'captcha',
                            'selector': '@src^captcha.php?sid=',
                            'type': 'src'
                        },
                        'input': {
                            'name': 'imagestring',
                            'type': 'text',
                            'selector': '@placeholder=CAPTCHA',
                            'required': True
                        },
                    },
                    'success_check': {
                        'name': 'login_result',
                        'selector': '@class$User_Name',
                        'type': 'text',
                        'expect_text': 'neilforest'
                    }
                },
                'extract_rules': [
                    {
                        'name': 'username',
                        'selector': '@class$User_Name',
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
                        'index': 5
                    },
                    {
                        'name': 'seeding_list_pagination',
                        'selector': '@class=nexus-pagination',
                        'type': 'text',
                        'need_pre_action': True
                    },
                    {
                        'name': 'seeding_list_row',
                        'selector': '@tag()=tr',
                        'location': 'grand-child',
                        'need_pre_action': True,
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
                        'name': 'bonus',
                        'selector': '@class=ucoin-notation',
                        'type': 'attribute',
                        'attribute': 'title'
                    },
                    {
                        'name': 'bonus_per_hour',
                        'selector': '@text():平均每次计算',
                        'type': 'by_day',
                        'need_pre_action': True,
                        'pre_action_type': 'goto',
                        'page_url': r'/mprecent.php?user={userid}'
                    },
                ],
                'checkin_config': 
                    {
                        'checkin_url': '/showup.php',
                        'checkin_button': {
                            'name': 'checkin_button',
                            'selector': '@href=showup.php',
                        },
                        # 'success_check': {
                        #     'element':{
                        #         'name': 'checkin_result',
                        #         'selector': '@tag()=h2',
                        #         'type': 'text'
                        #     },
                        #     'sign':{
                        #         'success': '签到成功',
                        #         'already': '今天已经签到过了',
                        #         'error': '签到失败',
                        #     }
                        # }
                    }
            }
            
            # 验证配置
            if not cls.validate_config(cls._config):
                raise ValueError(f"站点 {cls._config['site_id']} 的配置无效")
                
        return cls._config 