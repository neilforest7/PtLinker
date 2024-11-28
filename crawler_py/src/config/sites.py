import os

from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 获取登录凭据
USERNAME = os.getenv('LOGIN_USERNAME')
PASSWORD = os.getenv('LOGIN_PASSWORD')

if not USERNAME or not PASSWORD:
    raise ValueError("LOGIN_USERNAME 和 LOGIN_PASSWORD 必须在.env文件中设置")

# 站点URL配置
SITE_URLS = {
    'hdhome': 'https://hdhome.org',
    'ourbits': 'https://ourbits.club',
    'qingwapt': 'https://www.qingwapt.com',
    'hdfans': 'https://hdfans.org'
}

# 站点登录配置
SITE_CONFIGS = {
    'hdhome': {
        'login_url': 'https://hdhome.org/login.php',
        'form_selector': '@action=takelogin.php',
        'fields': {
            'username': {
                'name': 'username',
                'type': 'text',
                'selector': '@name=username',
                'value': USERNAME,
                'required': True
            },
            'password': {
                'name': 'password',
                'type': 'password',
                'selector': '@name=password',
                'value': PASSWORD,
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
                'type': 'submit',
                'selector': '@type=submit',
            }
        },
        'success_check': {
            'selector': '@class=User_Name',
            'expected_text': USERNAME
        }
    },
    'ourbits': {
        'login_url': 'https://ourbits.club/login.php',
        'form_selector': '@action=takelogin.php',
        'fields': {
            'username': {
                'name': 'username',
                'type': 'text',
                'selector': '@name=username',
                'value': USERNAME,
                'required': True
            },
            'password': {
                'name': 'password',
                'type': 'password',
                'selector': '@name=password',
                'value': PASSWORD,
                'required': True
            },
            'submit': {
                'name': 'submit',
                'type': 'submit',
                'selector': '@value=登录',
            }
        },
        'success_check': {
            'selector': '@class=User_Name',
            'expected_text': USERNAME
        }
    },
    'qingwapt': {
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
                'value': USERNAME,
                'required': True
            },
            'password': {
                'name': 'password',
                'type': 'password',
                'selector': '@name=password',
                'value': PASSWORD,
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
            'expected_text': USERNAME
        }
    },
    'hdfans': {
        'login_url': 'https://hdfans.org/login.php',
        'form_selector': '@action=takelogin.php',
        'fields': {
            'username': {
                'name': 'username',
                'type': 'text',
                'selector': '@name=username',
                'value': USERNAME,
                'required': True
            },
            'password': {
                'name': 'password',
                'type': 'password',
                'selector': '@name=password',
                'value': PASSWORD,
                'required': True
            },
            'submit': {
                'name': 'submit', 
                'type': 'submit',
                'selector': '@type=submit',
            }
        },
        'captcha': {
            'type': 'custom',
            'element': {
                'selector': '@alt=CAPTCHA',
                'type': 'src'
            },
            'input': {
                'name': 'imagestring',
                'type': 'text',
                'selector': '@name=imagestring',
                'required': True
            },
            'hash': {
                'name': 'imagehash',
                'type': 'text',
                'selector': '@name=imagehash',
                'targetField': 'imagehash'
            }
        },
        'success_check': {
            'selector': '@class=User_Name',
            'expected_text': USERNAME
        }
    }
}

# 数据提取规则
EXTRACT_RULES = {
    'hdhome': [
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
            'selector': '@text()=魔力值',
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
        {
            'name': 'hr_count',
            'selector': '@title=查看HR详情',
            'type': 'text'
        },
    ],
    'ourbits': [
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
            'selector': '@text()=魔力值',
            'location': 'next',
            'second_selector': '',
            'type': 'text'
        },
        {
            'name': 'hr_count',
            'selector': '@text()=H&R警告',
            'location': 'next',
            'second_selector': '',
            'type': 'text'
        },
    ],
    'qingwapt': [
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
    ],
    'hdfans': [
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
            'selector': '@text()=魔力值',
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
        {
            'name': 'hr_count',
            'selector': '@href^myhr.php',
            'type': 'text'
        },
    ]
} 