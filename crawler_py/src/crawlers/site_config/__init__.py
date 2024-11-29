"""
站点配置模块
此模块用于管理各个站点的配置信息
"""

from typing import Dict, Any

# 导入站点配置
from .hdhome import HDHomeConfig
from .ourbits import OurBitsConfig
from .qingwapt import QingwaPTConfig
from .hdfans import HDFansConfig
from .ubits import UBitsConfig
from .frds import FrdsConfig

# 聚合所有站点配置
SITE_CONFIGS: Dict[str, Dict[str, Any]] = {
    'hdhome': HDHomeConfig.get_config(),
    'ourbits': OurBitsConfig.get_config(),
    'qingwapt': QingwaPTConfig.get_config(),
    'hdfans': HDFansConfig.get_config(),
    'ubits': UBitsConfig.get_config(),
    'frds': FrdsConfig.get_config()
} 