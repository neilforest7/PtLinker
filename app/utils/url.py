from logging import Logger
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

from schemas.siteconfig import SiteConfigBase


def convert_url(task_config: SiteConfigBase, url: str, uid: Optional[str] = None) -> str:
    """
    将相对URL转换为绝对URL
    
    Args:
        task_config: 爬虫任务配置对象
        url: 原始URL
        uid: 用户ID
    Returns:
        str: 转换后的URL
    """
    if uid:
        url = url.replace('{userid}', uid)
    
    if not url:
        return url
        
    # 如果是相对路径，使用site_url[0]作为base_url
    if url.startswith('/'):
        if task_config.site_url and len(task_config.site_url) > 0:
            base_url = task_config.site_url[0]
            return urljoin(base_url, url)
            
    return url

def get_site_domain(task_config: SiteConfigBase, logger: Logger) -> str:
    """安全地获取站点域名"""
    try:
        # 获取站点URL
        site_url = task_config.site_url
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