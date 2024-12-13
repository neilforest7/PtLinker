from typing import Any, Dict, List, Optional
import json
from datetime import datetime

from DrissionPage import Chromium
from services.storage.storage_manager import StorageManager
from schemas.storage import StorageError
from core.logger import get_logger, setup_logger

class DataProcessError(Exception):
    """数据处理相关的异常"""
    pass

class DataHandler:
    """数据处理器，负责处理和存储爬取到的数据"""

    def __init__(self, task_config: Dict[str, Any]):
        """
        初始化数据处理器
        
        Args:
            task_config: 任务配置
                {
                    'task_id': str,  # 任务ID
                    'site_id': str,  # 站点ID
                    'storage': {      # 存储配置
                        'type': str,  # 存储类型
                        'base_dir': str,  # 基础目录
                        'compress': bool,  # 是否压缩
                        'backup': bool,    # 是否备份
                    }
                }
        """
        self.task_id = task_config.get('task_id', f'task-{int(datetime.now().timestamp())}')
        self.site_id = task_config.get('site_id', 'unknown')
        setup_logger()
        self.logger = get_logger(name=__name__, site_id=self.site_id)
        
        # 初始化存储管理器
        storage_config = task_config.get('storage', {
            'type': 'file',
            'base_dir': f"storage/data/{self.site_id}/{self.task_id}",
            'compress': True,
            'backup': True,
            'max_backups': 3
        })
        self.storage = StorageManager(storage_config)
        
        # 初始化统计信息
        self.stats = {
            'total_items': 0,
            'successful_items': 0,
            'failed_items': 0,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'errors': []
        }
        
        # 数据缓存
        self.items: List[Dict[str, Any]] = []
        self.batch_size = task_config.get('batch_size', 100)  # 批量保存的大小
        
        self.logger.info(f"数据处理器初始化完成 - 任务ID: {self.task_id}, 站点: {self.site_id}")
        self.logger.debug(f"存储配置: {storage_config}")

    async def process_item(self, item: Dict[str, Any]) -> bool:
        """
        处理单个数据项
        
        Args:
            item: 待处理的数据项
            
        Returns:
            bool: 处理是否成功
        """
        try:
            item_id = item.get('id', '未知ID')
            self.logger.info(f"开始处理数据项 [{item_id}]")
            self.logger.debug(f"原始数据: {json.dumps(item, ensure_ascii=False)}")
            
            # 数据验证
            self.logger.debug(f"开始验证数据项 [{item_id}]")
            if not await self._validate_item(item):
                self.logger.error(f"数据项 [{item_id}] 验证失败，跳过处理")
                await self._record_error(item_id, "数据验证失败")
                self.stats['failed_items'] += 1
                return False

            # 数据清洗和转换
            self.logger.debug(f"开始转换数据项 [{item_id}]")
            processed_item = await self._transform_item(item)
            self.logger.debug(f"数据转换完成 [{item_id}]: {json.dumps(processed_item, ensure_ascii=False)}")

            # 添加元数据
            processed_item['_metadata'] = {
                'task_id': self.task_id,
                'site_id': self.site_id,
                'processed_at': datetime.now().isoformat(),
                'version': '1.0'
            }

            # 存储数据
            self.items.append(processed_item)
            self.stats['successful_items'] += 1
            self.stats['total_items'] += 1
            
            # 检查是否需要批量保存
            if len(self.items) >= self.batch_size:
                await self._save_batch()
            
            self.logger.success(f"数据项 [{item_id}] 处理成功")
            self.logger.debug(f"当前统计: 成功={self.stats['successful_items']}, "
                            f"失败={self.stats['failed_items']}, "
                            f"总数={self.stats['total_items']}")
            return True

        except Exception as e:
            self.logger.error("处理数据项失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            await self._record_error(item.get('id', '未知ID'), str(e))
            self.stats['failed_items'] += 1
            return False

    async def _validate_item(self, item: Dict[str, Any]) -> bool:
        """
        验证数据项的完整性和有效性
        """
        required_fields = ['id', 'title', 'url']
        item_id = item.get('id', '未知ID')
        
        self.logger.debug(f"验证数据项 [{item_id}] 的必需字段: {required_fields}")
        
        # 检查所有必需字段
        for field in required_fields:
            if field not in item:
                self.logger.warning(f"数据项 [{item_id}] 缺少字段: {field}")
                return False
            if not item[field]:
                self.logger.warning(f"数据项 [{item_id}] 字段 {field} 为空")
                return False
        
        # 验证URL格式
        if not item['url'].startswith(('http://', 'https://')):
            self.logger.warning(f"数据项 [{item_id}] URL格式无效: {item['url']}")
            return False
                
        self.logger.debug(f"数据项 [{item_id}] 验证通过")
        return True

    async def _transform_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换和清洗数据项
        """
        item_id = item.get('id', '未知ID')
        self.logger.debug(f"开始转换数据项 [{item_id}]")
        
        # 创建新的数据项，避免修改原始数据
        processed_item = item.copy()
        
        # 标准化日期时间字段
        datetime_fields = ['created_at', 'updated_at', 'publish_time']
        for field in datetime_fields:
            if field in processed_item:
                self.logger.debug(f"处理日期时间字段 [{item_id}] {field}: {processed_item[field]}")
                try:
                    if isinstance(processed_item[field], str):
                        # 处理常见的日期格式
                        processed_item[field] = await self._normalize_datetime(processed_item[field])
                    self.logger.debug(f"日期时间标准化完成 [{item_id}] {field}: {processed_item[field]}")
                except Exception as e:
                    self.logger.warning(f"日期时间标准化失败 [{item_id}] {field}: {str(e)}")
                    processed_item[field] = datetime.now().isoformat()

        # 确保数值字段为正确类型
        numeric_fields = ['size', 'seeders', 'leechers', 'completed']
        for field in numeric_fields:
            if field in processed_item:
                self.logger.debug(f"处理数值字段 [{item_id}] {field}: {processed_item[field]}")
                try:
                    original_value = processed_item[field]
                    processed_item[field] = int(float(str(processed_item[field]).replace(',', '')))
                    self.logger.debug(f"数值转换成功 [{item_id}] {field}: {original_value} -> {processed_item[field]}")
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"数值字段转换失败 [{item_id}] {field}: {str(e)}")
                    processed_item[field] = 0

        # 清理和规范化标签
        if 'tags' in processed_item:
            self.logger.debug(f"处理标签字段 [{item_id}]")
            processed_item['tags'] = await self._normalize_tags(processed_item['tags'])

        self.logger.debug(f"数据项转换完成 [{item_id}]")
        return processed_item

    async def _normalize_datetime(self, dt_str: str) -> str:
        """标准化日期时间字符串"""
        # 移除时区信息
        dt_str = dt_str.replace('Z', '+00:00')
        # 尝试解析不同格式
        try:
            return datetime.fromisoformat(dt_str).isoformat()
        except ValueError:
            # 可以添加更多日期格式的处理
            self.logger.warning(f"无法解析日期时间: {dt_str}")
            return datetime.now().isoformat()

    async def _normalize_tags(self, tags: Any) -> List[str]:
        """标准化标签列表"""
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',')]
        elif isinstance(tags, (list, tuple)):
            tags = [str(t).strip() for t in tags]
        else:
            tags = []
        return [t for t in tags if t]  # 移除空标签

    async def _record_error(self, item_id: str, error_msg: str) -> None:
        """记录错误信息"""
        error_info = {
            'item_id': item_id,
            'error': error_msg,
            'timestamp': datetime.now().isoformat()
        }
        self.stats['errors'].append(error_info)
        
        # 如果错误太多，只保留最近的1000条
        if len(self.stats['errors']) > 1000:
            self.stats['errors'] = self.stats['errors'][-1000:]

    async def _save_batch(self) -> bool:
        """批量保存数据"""
        if not self.items:
            return True
            
        try:
            self.logger.info(f"开始批量保存数据，数量: {len(self.items)}")
            
            # 准备保存的数据
            batch_data = {
                'task_id': self.task_id,
                'site_id': self.site_id,
                'batch_time': datetime.now().isoformat(),
                'items': self.items
            }
            
            # 生成文件名
            filename = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # 保存数据
            await self.storage.save(batch_data, filename)
            
            # 清空缓存
            self.items = []
            
            self.logger.success(f"批量保存完成: {filename}")
            return True
            
        except StorageError as e:
            self.logger.error("批量保存失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return False

    async def save_all(self) -> bool:
        """保存所有数据和统计信息"""
        try:
            # 保存剩余的数据项
            if self.items:
                if not await self._save_batch():
                    return False
            
            # 更新统计信息
            self.stats['end_time'] = datetime.now().isoformat()
            
            # 保存统计信息
            await self.storage.save(
                self.stats,
                f"stats_{self.task_id}.json",
                backup=True
            )
            
            self.logger.success("所有数据保存完成")
            self.logger.info(f"总统计: 成功={self.stats['successful_items']}, "
                            f"失败={self.stats['failed_items']}, "
                            f"总数={self.stats['total_items']}")
            return True
            
        except Exception as e:
            self.logger.error("保存数据失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return False
    async def get_stats(self) -> Dict[str, Any]:
        """获取数据处理统计信息"""
        self.logger.debug(f"获取统计信息: {json.dumps(self.stats, ensure_ascii=False)}")
        return self.stats

    async def clear_data(self) -> None:
        """清除所有已处理的数据"""
        self.logger.info(f"清除数据 - 当前项目数: {len(self.items)}")
        self.logger.debug(f"清除前统计: {json.dumps(self.stats, ensure_ascii=False)}")
        
        self.items.clear()
        self.stats = {
            'total_items': 0,
            'successful_items': 0,
            'failed_items': 0,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'errors': []
        }
        
        self.logger.debug("数据清除完成")
        self.logger.debug(f"清除后统计: {json.dumps(self.stats, ensure_ascii=False)}")

    async def load_cookies(self) -> Optional[Dict[str, Any]]:
        """
        加载cookies和浏览器状态
        
        Returns:
            Optional[Dict[str, Any]]: 包含cookies和浏览器状态的字典，加载失败返回None
        """
        try:
            self.logger.info("开始加载cookies和浏览器状态")
            
            # 尝试加载状态数据，如果失败会自动尝试从备份加载
            state_data = await self.state_storage.load(f"cookies/{self.site_id}.json")
            
            if not state_data or 'cookies' not in state_data:
                self.logger.warning("未找到有效的cookies数据")
                return None
            
            # 检查cookies是否过期
            timestamp = datetime.fromisoformat(state_data['timestamp'])
            if (datetime.now() - timestamp).days > 7:  # cookies超过7天视为过期
                self.logger.warning("Cookies已过期")
                return None
                
            self.logger.success("Cookies和浏览器状态加载成功")
            self.logger.debug(f"Cookies数量: {len(state_data['cookies'])}")
            
            return state_data
            
        except Exception as e:
            self.logger.error("加载cookies失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return None

    async def validate_cookies(self, page: Chromium) -> bool:
        """
        验证cookies是否有效
        
        Args:
            page: Playwright页面对象
            
        Returns:
            bool: cookies是否有效
        """
        try:
            self.logger.info("开始验证cookies")
            
            # 加载cookies
            state_data = await self.load_cookies()
            if not state_data:
                self.logger.warning("无法加载cookies，验证失败")
                return False
            
            # 设置cookies
            await page.context.add_cookies(state_data['cookies'])
            self.logger.debug("Cookies已设置到浏览器")
            
            # 访问首页验证登录状态
            self.logger.debug(f"访问首页验证: {self.site_config['home_url']}")
            await page.goto(self.site_config['home_url'])
            await page.wait_for_load_state('networkidle')
            
            # 检查登录状态
            is_valid = await page.locator(self.site_config['login_check_selector']).count() > 0
            
            if is_valid:
                self.logger.success("Cookies验证成功，登录状态有效")
            else:
                self.logger.warning("Cookies验证失败，登录状态无效")
            
            return is_valid
            
        except Exception as e:
            self.logger.error("验证cookies失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return False

