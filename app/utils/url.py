from logging import Logger
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

from schemas.siteconfig import SiteConfigBase


def convert_url(site_url: str, short_url: str, uid: Optional[str] = None) -> str:
    """
    将相对URL转换为绝对URL
    
    Args:
        site_url: 站点URL
        short_url: 短URL
        uid: 用户ID
    Returns:
        str: 转换后的URL
    """
    if uid:
        short_url = short_url.replace('{userid}', uid)
        site_url = site_url.replace('{userid}', uid)
    
    # 确保site_url不为空
    if not site_url:
        return short_url
        
    # 如果short_url是完整的URL，直接返回
    if short_url.startswith(('http://', 'https://')):
        return short_url
        
    # 移除site_url末尾的斜杠（如果有）
    base_url = site_url.rstrip('/')
    
    # 如果short_url以斜杠开头，确保它不会有双斜杠
    if short_url.startswith('/'):
        short_url = short_url.lstrip('/')
        
    # 拼接URL
    return f"{base_url}/{short_url}"

def get_site_domain(site_url: str, logger: Logger) -> str:
    """安全地获取站点域名"""
    try:
        # 获取站点URL
        if not site_url:
            logger.error("站点URL未配置")
            return ""
            
        # 确保site_url是列表且不为空
        if not isinstance(site_url, (list, tuple)) or not site_url:
            logger.error(f"站点URL格式错误: {site_url}")
            return ""
            
        # 解析URL
        parsed_url = urlparse(site_url[0])
        if not parsed_url.netloc:
            logger.error(f"无法从URL解析出域名: {site_url[0]}")
            return ""
            
        return parsed_url.netloc
        
    except Exception as e:
        logger.error(f"获取站点域名失败: {str(e)}")
        return ""