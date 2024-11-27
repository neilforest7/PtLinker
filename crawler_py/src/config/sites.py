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
        'form_selector': 'form[action="takelogin.php"]',
        'fields': {
            'username': {
                'name': 'username',
                'type': 'text',
                'selector': '@name="username"',
                'value': USERNAME,
                'required': True
            },
            'password': {
                'name': 'password',
                'type': 'password',
                'selector': '@name="password"',
                'value': PASSWORD,
                'required': True
            }
        },
        'success_check': {
            'selector': 'a.User_Name',
            'expected_text': USERNAME
        }
    },
    'qingwapt': {
        'login_url': 'https://www.qingwapt.com/login.php',
        'form_selector': 'form[action="takelogin.php"]',
        'fields': {
            'username': {
                'name': 'username',
                'type': 'text',
                'selector': '@name="username" @type="text"',
                'value': USERNAME,
                'required': True
            },
            'password': {
                'name': 'password',
                'type': 'password',
                'selector': '@name="password" @type="password"',
                'value': PASSWORD,
                'required': True
            }
        },
        'captcha': {
            'type': 'custom',
            'element': {
                'selector': 'img[src*="image.php?action=regimage"]',
                'type': 'img'
            },
            'input': {
                'name': 'imagestring',
                'type': 'text',
                'selector': 'input[name="imagestring"]',
                'required': True
            },
            'hash': {
                'selector': 'input[name="imagehash"]',
                'targetField': 'imagehash'
            }
        },
        'success_check': {
            'selector': '#info_block a.User_Name',
            'expected_text': USERNAME
        }
    },
    'hdfans': {
        'login_url': 'https://hdfans.org/login.php',
        'form_selector': 'form[action="takelogin.php"]',
        'fields': {
            'username': {
                'name': 'username',
                'type': 'text',
                'selector': '@name="username"',
                'value': USERNAME,
                'required': True
            },
            'password': {
                'name': 'password',
                'type': 'password',
                'selector': '@name="password"',
                'value': PASSWORD,
                'required': True
            }
        },
        'captcha': {
            'type': 'custom',
            'element': {
                'selector': 'img[src*="image.php?action=regimage"]',
                'type': 'img'
            },
            'input': {
                'name': 'imagestring',
                'type': 'text',
                'selector': '@name="imagestring"',
                'required': True
            },
            'hash': {
                'selector': '@name="imagehash"',
                'targetField': 'imagehash'
            }
        },
        'success_check': {
            'selector': 'a.User_Name b',
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
        {
            'name': 'seed_subpage',
            'selector': '@href^javascript: getusertorrentlistajax',
            'type': 'text'
        },
    ],
    'ourbits': [
        {
            'name': 'username',
            'selector': 'a.User_Name',
            'type': 'text',
            'required': True
        },
        {
            'name': 'user_class',
            'selector': 'img[alt*="class="]',
            'type': 'attribute',
            'attribute': 'alt',
            'transform': 'extract_class'
        },
        {
            'name': 'join_time',
            'selector': 'td:has-text("加入时间") + td',
            'type': 'text'
        },
        {
            'name': 'upload',
            'selector': 'td:has-text("上传量") + td',
            'type': 'text'
        },
        {
            'name': 'download',
            'selector': 'td:has-text("下载量") + td',
            'type': 'text'
        },
        {
            'name': 'ratio',
            'selector': 'td:has-text("分享率") + td',
            'type': 'text'
        },
        {
            'name': 'bonus',
            'selector': 'td:has-text("魔力值") + td',
            'type': 'text'
        }
    ],
    'qingwapt': [
        {
            'name': 'username',
            'selector': '#info_block a.User_Name',
            'type': 'text',
            'required': True
        },
        {
            'name': 'user_class',
            'selector': '#info_block img[alt*="class="]',
            'type': 'attribute',
            'attribute': 'alt',
            'transform': 'extract_class'
        },
        {
            'name': 'join_time',
            'selector': '#info_block td:has-text("加入时间") + td',
            'type': 'text'
        },
        {
            'name': 'upload',
            'selector': '#info_block td:has-text("上传量") + td',
            'type': 'text'
        },
        {
            'name': 'download',
            'selector': '#info_block td:has-text("下载量") + td',
            'type': 'text'
        },
        {
            'name': 'ratio',
            'selector': '#info_block td:has-text("分享率") + td',
            'type': 'text'
        },
        {
            'name': 'bonus',
            'selector': '#info_block td:has-text("魔力值") + td',
            'type': 'text'
        }
    ],
    'hdfans': [
        {
            'name': 'username',
            'selector': 'a.User_Name',
            'type': 'text',
            'required': True
        },
        {
            'name': 'user_class',
            'selector': 'img[alt*="class="]',
            'type': 'attribute',
            'attribute': 'alt',
            'transform': 'extract_class'
        },
        {
            'name': 'join_time',
            'selector': 'td:has-text("加入时间") + td',
            'type': 'text'
        },
        {
            'name': 'upload',
            'selector': 'td:has-text("上传量") + td',
            'type': 'text'
        },
        {
            'name': 'download',
            'selector': 'td:has-text("下载量") + td',
            'type': 'text'
        },
        {
            'name': 'ratio',
            'selector': 'td:has-text("分享率") + td',
            'type': 'text'
        },
        {
            'name': 'bonus',
            'selector': 'td:has-text("魔力值") + td',
            'type': 'text'
        }
    ]
} 