from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.sqlalchemy.models import CrawlerConfig
from app.models.pydantic.schemas import ConfigTemplate, CrawlerConfig as ConfigSchema
from typing import Dict, Any, List, Optional
import json
import re
from playwright.async_api import async_playwright

class ConfigService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def list_configs(
        self,
        skip: int = 0,
        limit: int = 10,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        query = select(CrawlerConfig).filter(
            CrawlerConfig.is_template == False
        )
        
        if category:
            query = query.filter(CrawlerConfig.category == category)
        if tags:
            query = query.filter(CrawlerConfig.tags.contains(tags))
            
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def list_templates(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        query = select(CrawlerConfig).filter(
            CrawlerConfig.is_template == True
        )
        
        if category:
            query = query.filter(CrawlerConfig.category == category)
        if tags:
            query = query.filter(CrawlerConfig.tags.contains(tags))
            
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def validate_config(self, config: ConfigSchema) -> Dict[str, Any]:
        errors = []
        warnings = []
        
        try:
            # 验证起始 URL 可访问性
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                
                for url in config.start_urls:
                    try:
                        response = await page.goto(str(url))
                        if not response.ok:
                            errors.append(f"URL {url} returned status {response.status}")
                    except Exception as e:
                        errors.append(f"Failed to access {url}: {str(e)}")
                
                # 验证选择器
                for rule_name, rule in config.page_rules.items():
                    for field, selector in rule.selectors.items():
                        try:
                            if selector.type == "css":
                                elements = await page.query_selector_all(selector.value)
                                if not elements and not selector.optional:
                                    warnings.append(
                                        f"Selector '{field}' in rule '{rule_name}' "
                                        f"found no elements"
                                    )
                        except Exception as e:
                            errors.append(
                                f"Invalid selector '{field}' in rule '{rule_name}': "
                                f"{str(e)}"
                            )
                
                await browser.close()
            
            # 验证登录配置
            if config.login:
                if not all([
                    config.login.username,
                    config.login.password,
                    config.login.username_selector,
                    config.login.password_selector,
                    config.login.submit_selector
                ]):
                    errors.append("Incomplete login configuration")
            
            # 验证代理配置
            if config.proxy:
                proxy_pattern = r'^(http|https|socks5)://[\w\-.]+(:\d+)?$'
                if not re.match(proxy_pattern, config.proxy):
                    errors.append("Invalid proxy format")
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    async def test_config(self, config: ConfigSchema) -> Dict[str, Any]:
        results = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            # 设置视口大小
            await page.set_viewport_size(config.viewport)
            
            # 设置用户代理
            if config.user_agent:
                await page.set_extra_http_headers({
                    "User-Agent": config.user_agent
                })
            
            # 处理登录
            if config.login:
                try:
                    await self._handle_login(page, config.login)
                    results.append({
                        "step": "login",
                        "status": "success"
                    })
                except Exception as e:
                    results.append({
                        "step": "login",
                        "status": "failed",
                        "error": str(e)
                    })
                    return {"results": results}
            
            # 测试每个页面规则
            for rule_name, rule in config.page_rules.items():
                try:
                    await page.goto(str(config.start_urls[0]))
                    
                    # 等待指定元素
                    if rule.wait_for:
                        await page.wait_for_selector(rule.wait_for)
                    
                    # 执行自定义脚本
                    if rule.scripts:
                        for script in rule.scripts:
                            await page.evaluate(script)
                    
                    # 测试选择器
                    data = {}
                    for field, selector in rule.selectors.items():
                        try:
                            if selector.type == "css":
                                elements = await page.query_selector_all(selector.value)
                                data[field] = len(elements)
                        except Exception as e:
                            data[field] = f"Error: {str(e)}"
                    
                    results.append({
                        "step": f"rule_{rule_name}",
                        "status": "success",
                        "data": data
                    })
                    
                except Exception as e:
                    results.append({
                        "step": f"rule_{rule_name}",
                        "status": "failed",
                        "error": str(e)
                    })
            
            await browser.close()
        
        return {"results": results}