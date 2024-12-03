from urllib.parse import urljoin
from typing import Dict, Any, Optional
from models.crawler import CrawlerTaskConfig

def convert_url(task_config: CrawlerTaskConfig, url: str, uid: Optional[str] = None) -> str:
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
