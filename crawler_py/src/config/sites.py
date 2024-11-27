import os

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
        'form_selector': 'form[action="takelogin.php"]',
        'fields': {
            'username': {
                'name': 'username',
                'type': 'text',
                'selector': 'input[name="username"]',
                'value': os.getenv('LOGIN_USERNAME'),
                'required': True
            },
            'password': {
                'name': 'password',
                'type': 'password',
                'selector': 'input[name="password"]',
                'value': os.getenv('LOGIN_PASSWORD'),
                'required': True
            }
        },
        'success_check': {
            'selector': 'a.User_Name',
            'expected_text': str(os.getenv('LOGIN_USERNAME'))
        }
    },
    'ourbits': {
        'login_url': 'https://ourbits.club/login.php',
        'form_selector': 'form[action="takelogin.php"]',
        'fields': {
            'username': {
                'name': 'username',
                'type': 'text',
                'selector': 'input[name="username"]',
                'value': os.getenv('LOGIN_USERNAME'),
                'required': True
            },
            'password': {
                'name': 'password',
                'type': 'password',
                'selector': 'input[name="password"]',
                'value': os.getenv('LOGIN_PASSWORD'),
                'required': True
            }
        },
        'success_check': {
            'selector': 'a.User_Name',
            'expected_text': str(os.getenv('LOGIN_USERNAME'))
        }
    },
    'qingwapt': {
        'login_url': 'https://www.qingwapt.com/login.php',
        'form_selector': 'form[action="takelogin.php"]',
        'fields': {
            'username': {
                'name': 'username',
                'type': 'text',
                'selector': 'input.textbox[name="username"][type="text"]',
                'value': os.getenv('LOGIN_USERNAME'),
                'required': True
            },
            'password': {
                'name': 'password',
                'type': 'password',
                'selector': 'input.textbox[name="password"][type="password"]',
                'value': os.getenv('LOGIN_PASSWORD'),
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
            'expected_text': os.getenv('LOGIN_USERNAME')
        }
    },
    'hdfans': {
        'login_url': 'https://hdfans.org/login.php',
        'form_selector': 'form[action="takelogin.php"]',
        'fields': {
            'username': {
                'name': 'username',
                'type': 'text',
                'selector': 'input[name="username"]',
                'value': os.getenv('LOGIN_USERNAME'),
                'required': True
            },
            'password': {
                'name': 'password',
                'type': 'password',
                'selector': 'input[name="password"]',
                'value': os.getenv('LOGIN_PASSWORD'),
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
        },
        'success_check': {
            'selector': 'a.User_Name b',
            'expected_text': str(os.getenv('LOGIN_USERNAME'))
        }
    }
}

# 数据提取规则
EXTRACT_RULES = {
    'hdhome': [
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