import os
import platform
import zipfile
import requests
from pathlib import Path
from typing import Any, Dict, Optional

from core.logger import get_logger, setup_logger
from dotenv import load_dotenv
from models.settings import Settings as DBSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 加载.env文件
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

class SettingManager:
    """设置管理器"""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not SettingManager._initialized:
            self._settings: Optional[DBSettings] = None
            self._cache: Dict[str, Any] = {}
            SettingManager._initialized = True
            # setup_logger()
            self.logger = get_logger(name=__name__, site_id="SettingMgr")
    
    @classmethod
    def get_instance(cls) -> 'SettingManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
            
    def _get_env_value(self, key: str) -> Any:
        """从环境变量获取配置值"""
        value = os.getenv(key.upper())
        if value is None:
            return None
            
        if key.upper() in ['CAPTCHA_SKIP_SITES', 'CHECKIN_SITES']:
            return value
        
        # 转换布尔值
        if value.lower() in ['true', 'false']:
            return value.lower() == 'true'
        
        # 转换整数
        try:
            return int(value)
        except ValueError:
            pass
            
        return value
    
    async def initialize(self, db: AsyncSession) -> None:
        """初始化设置管理器
        
        优先级顺序：
        1. 数据库中的现有设置
        2. 环境变量中的设置
        3. 模型定义的默认值
        """
        try:
            # 1. 获取最新的配置
            stmt = select(DBSettings).order_by(DBSettings.updated_at.desc()).limit(1)
            result = await db.execute(stmt)
            settings = result.scalar_one_or_none()
            
            # 2. 如果数据库中没有配置，创建新的配置实例
            if not settings:
                self.logger.info("No settings found in database, creating new settings")
                settings = DBSettings()
                is_new = True
            else:
                self.logger.info("Found existing settings in database")
                is_new = False
            
            # 3. 获取所有可配置的字段
            settable_fields = [
                column.key for column in DBSettings.__table__.columns
                if not column.key.startswith('_')
            ]
            
            # 4. 如果是新配置，从环境变量和默认值初始化
            if is_new:
                for field in settable_fields:
                    # 首先尝试从环境变量获取
                    env_value = self._get_env_value(field)
                    if env_value is not None:
                        setattr(settings, field, env_value)
                        self.logger.debug(f"Setting {field} initialized from .env: {env_value}")
                    else:
                        # 使用模型定义的默认值
                        current_value = getattr(settings, field, None)
                        if current_value is not None:
                            self.logger.debug(f"Setting {field} using default value: {current_value}")
                
                # 保存新配置到数据库
                db.add(settings)
                await db.commit()
                self.logger.info("New settings saved to database")
            else:
                # 5. 如果是现有配置，记录日志但不修改值
                for field in settable_fields:
                    current_value = getattr(settings, field, None)
                    env_value = self._get_env_value(field)
                    if env_value is not None and env_value != current_value:
                        self.logger.debug(
                            f"Note: Environment variable for {field} ({env_value}) "
                            f"differs from database value ({current_value})"
                        )
            
            # 6. 保存到实例并清空缓存
            self._settings = settings
            self._cache.clear()
            
            # 7. 检查并确保 Chrome 存在
            chrome_path = await self.ensure_chrome_exists(db)
            if not chrome_path:
                self.logger.warning("Failed to ensure Chrome exists during initialization")
            else:
                self.logger.info(f"Chrome verified at: {os.path.abspath(chrome_path)}")
                
                            
            # 设置DrissionPage的Chrome可执行文件路径
            import DrissionPage
            DrissionPage.ChromiumOptions().set_browser_path(os.path.abspath(chrome_path)).save()
            self.logger.info(f"DrissionPage的Chrome可执行文件路径已设置为: {chrome_path}")
            
            self.logger.info(
                "Settings initialized successfully "
                f"({'new settings created' if is_new else 'existing settings loaded'})"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to initialize settings: {str(e)}", exc_info=True)
            raise
    
    async def get_setting(self, key: str) -> Any | list[str]:
        """
        获取配置值
        
        如果配置项为列表,如CAPTCHA_SKIP_SITES, CHECKIN_SITES, 则返回列表
        """
        # 先从缓存获取
        if key in self._cache:
            return self._cache[key]
            
        if not self._settings:
            raise RuntimeError("Settings not initialized. Call initialize() first.")
            
        # 从数据库配置获取
        value = getattr(self._settings, key, None)
        if value is not None:
            self._cache[key] = value
        
        # 如果配置项为列表,如CAPTCHA_SKIP_SITES, CHECKIN_SITES, 则返回列表
        if key.upper() in ['CAPTCHA_SKIP_SITES', 'CHECKIN_SITES']:
            value: list[str] = value.split(',')
            return value
        
        return value
    
    async def set_setting(self, db: AsyncSession, key: str, value: Any) -> None:
        """设置配置值"""
        if not self._settings:
            raise RuntimeError("Settings not initialized. Call initialize() first.")
            
        try:
            # 检查属性是否存在
            if not hasattr(self._settings, key):
                raise ValueError(f"Invalid setting key: {key}")
                
            # 设置新值
            setattr(self._settings, key, value)
            await db.commit()
            
            # 更新缓存
            self._cache[key] = value
            self.logger.debug(f"Setting updated: {key} = {value}")
            
        except Exception as e:
            await db.rollback()
            self.logger.error(f"Failed to update setting: {str(e)}", exc_info=True)
            raise
    
    async def get_all_settings(self) -> Dict[str, Any]:
        """获取所有配置"""
        if not self._settings:
            raise RuntimeError("Settings not initialized. Call initialize() first.")
            
        return {
            column.key: getattr(self._settings, column.key)
            for column in self._settings.__table__.columns
            if not column.key.startswith('_')
        }
    
    async def update_settings(self, db: AsyncSession, settings: Dict[str, Any]) -> None:
        """批量更新配置"""
        if not self._settings:
            raise RuntimeError("Settings not initialized. Call initialize() first.")
            
        try:
            # 获取当前会话中的设置对象
            stmt = select(DBSettings).where(DBSettings.id == self._settings.id)
            result = await db.execute(stmt)
            current_settings = result.scalar_one()
            
            # 处理需要去重的字段
            list_fields = ['captcha_skip_sites', 'checkin_sites']
            for field in list_fields:
                if field in settings:
                    # 将字符串分割成列表,去重,再合并回字符串
                    if settings[field]:
                        items = settings[field].split(',')
                        # 去除空字符串并去重
                        unique_items = list(dict.fromkeys(item.strip() for item in items if item.strip()))
                        settings[field] = ','.join(unique_items)
                    else:
                        settings[field] = ''
            
            # 更新实例属性
            for key, value in settings.items():
                if hasattr(current_settings, key):
                    setattr(current_settings, key, value)
                    self._cache[key] = value
            
            # 更新内存中的实例
            self._settings = current_settings
            
            # 提交更改
            await db.commit()
            self.logger.info("Settings updated successfully")
            
        except Exception as e:
            await db.rollback()
            self.logger.error(f"Failed to update settings: {str(e)}", exc_info=True)
            raise
    
    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache.clear()
        self.logger.debug("Settings cache cleared")

    # 便捷属性访问方法
    @property
    def crawler_max_concurrency(self) -> int:
        """获取爬虫最大并发数"""
        return self._settings.crawler_max_concurrency if self._settings else 15

    @property
    def fresh_login(self) -> bool:
        """获取是否强制重新登录"""
        return self._settings.fresh_login if self._settings else False

    @property
    def chrome_path(self) -> Optional[str]:
        """获取Chrome浏览器路径"""
        return self._settings.chrome_path if self._settings else None

    @property
    def headless(self) -> bool:
        """获取是否使用无头模式"""
        return self._settings.headless if self._settings else True

    @property
    def log_level(self) -> str:
        """获取日志级别"""
        return self._settings.log_level if self._settings else "DEBUG"

    @property
    def enable_checkin(self) -> bool:
        """获取是否启用签到"""
        return self._settings.enable_checkin if self._settings else True

    @property
    def captcha_api_key(self) -> Optional[str]:
        """获取验证码API密钥"""
        return self._settings.captcha_api_key if self._settings else None

    @property
    def captcha_default_method(self) -> str:
        """获取验证码处理方法"""
        return self._settings.captcha_default_method if self._settings else "api"

    async def reset_settings(self, db: AsyncSession) -> None:
        """重置所有设置到环境变量和默认值
        
        重置顺序：
        1. 清除现有设置
        2. 从环境变量加载设置
        3. 使用模型定义的默认值
        4. 保存到数据库
        5. 确保 Chrome 存在
        """
        try:
            self.logger.info("Starting settings reset process")
            
            # 1. 创建新的设置实例（使用模型默认值）
            new_settings = DBSettings()
            
            # 2. 获取所有可配置字段
            settable_fields = [
                column.key for column in DBSettings.__table__.columns
                if not column.key.startswith('_')
            ]
            
            # 3. 从环境变量加载设置
            for field in settable_fields:
                env_value = self._get_env_value(field)
                if env_value is not None:
                    setattr(new_settings, field, env_value)
                    self.logger.debug(f"Reset {field} to env value: {env_value}")
                else:
                    default_value = getattr(new_settings, field, None)
                    self.logger.debug(f"Reset {field} to default value: {default_value}")
            
            # 4. 删除现有设置
            stmt = select(DBSettings)
            result = await db.execute(stmt)
            existing_settings = result.scalars().all()
            for setting in existing_settings:
                await db.delete(setting)
            
            # 5. 保存新设置到数据库
            db.add(new_settings)
            await db.commit()
            
            # 6. 更新实例和缓存
            self._settings = new_settings
            self._cache.clear()
            
            # 7. 检查并确保 Chrome 存在
            chrome_path = await self.ensure_chrome_exists(db)
            if not chrome_path:
                self.logger.warning("Failed to ensure Chrome exists during settings reset")
            else:
                self.logger.info(f"Chrome verified at: {chrome_path}")
            
            # 设置DrissionPage的Chrome可执行文件路径
            import DrissionPage
            DrissionPage.ChromiumOptions().set_browser_path(os.path.abspath(chrome_path)).save()
            self.logger.info(f"DrissionPage的Chrome可执行文件路径已设置为: {chrome_path}")
            
            self.logger.info("Settings have been reset successfully")
            
        except Exception as e:
            await db.rollback()
            self.logger.error(f"Failed to reset settings: {str(e)}", exc_info=True)
            raise

    async def ensure_chrome_exists(self, db: AsyncSession) -> Optional[str]:
        """确保 Chrome 存在，如果不存在则下载便携版"""
        try:
            # 先检查数据库中配置的路径
            chrome_path = await self.get_setting('chrome_path')
            if chrome_path and Path(chrome_path).exists():
                return chrome_path

            # 确定下载目录
            storage_path = await self.get_setting('storage_path')
            chrome_dir = Path(storage_path) / 'chrome'
            chrome_dir.mkdir(parents=True, exist_ok=True)

            # 根据操作系统选择下载配置
            system = platform.system().lower()
            if system == 'windows':
                platform_path = 'Win_x64'
                chrome_exe = chrome_dir / 'chrome-win' / 'chrome.exe'
                chrome_app = chrome_exe
                zip_name = 'chrome-win.zip'
            elif system == 'darwin':
                arch = platform.machine()
                if arch == 'arm64':
                    platform_path = 'Mac_Arm64'
                else:
                    platform_path = 'Mac'
                chrome_app = chrome_dir / 'chrome-mac' / 'Chromium.app'
                chrome_exe = chrome_app / 'Contents' / 'MacOS' / 'Chromium'
                zip_name = 'chrome-mac.zip'
            elif system == 'linux':
                platform_path = 'Linux_x64'
                chrome_exe = chrome_dir / 'chrome-linux' / 'chrome'
                chrome_app = chrome_exe
                zip_name = 'chrome-linux.zip'
            else:
                raise NotImplementedError(f"Unsupported system: {system}")

            zip_path = chrome_dir / zip_name

            if not chrome_app.exists():
                # 检查是否已有压缩包
                need_download = True
                if zip_path.exists() and zip_path.stat().st_size > 0:
                    try:
                        # 验证现有zip文件完整性
                        with zipfile.ZipFile(zip_path, 'r') as zf:
                            if zf.testzip() is None:
                                self.logger.info(f"Found existing Chrome package at {zip_path}")
                                need_download = False
                            else:
                                self.logger.warning("Existing Chrome package is corrupted, will download again")
                                zip_path.unlink()
                    except zipfile.BadZipFile:
                        self.logger.warning("Existing Chrome package is invalid, will download again")
                        zip_path.unlink()

                if need_download:
                    # 获取最新版本号
                    version_url = f"https://storage.googleapis.com/chromium-browser-snapshots/{platform_path}/LAST_CHANGE"
                    self.logger.info(f"Getting latest Chrome version from {version_url}")
                    response = requests.get(version_url)
                    if not response.ok:
                        raise Exception(f"Failed to get latest version: {response.status_code}")
                    latest_version = response.text.strip()
                    
                    # 构建下载URL
                    download_url = f"https://storage.googleapis.com/chromium-browser-snapshots/{platform_path}/{latest_version}/{zip_name}"
                    self.logger.info(f"Downloading Chrome version {latest_version} from {download_url}")
                    
                    # 下载Chrome
                    response = requests.get(download_url, stream=True)
                    if not response.ok:
                        raise Exception(f"Download failed with status code: {response.status_code}")

                    # 获取文件大小
                    total_size = int(response.headers.get('content-length', 0))

                    # 下载文件并显示进度
                    block_size = 1024 * 1024  # 1MB
                    downloaded_size = 0

                    with open(zip_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=block_size):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                progress = (downloaded_size / total_size) * 100
                                self.logger.debug(f"Download progress: {progress:.1f}%")

                # 解压Chrome
                self.logger.info("Extracting Chrome...")
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        zf.extractall(chrome_dir)
                except zipfile.BadZipFile as e:
                    raise Exception(f"Failed to extract Chrome package: {str(e)}")

                # 设置执行权限
                if system in ['linux', 'darwin']:
                    if system == 'darwin':
                        # Mac 平台设置应用程序包的权限
                        os.system(f'xattr -rd com.apple.quarantine "{chrome_app}"')
                        # 递归设置执行权限
                        os.system(f'chmod -R +x "{chrome_app}"')
                    else:
                        # Linux 只需要设置可执行文件权限
                        chrome_exe.chmod(0o755)

                # 验证应用是否存在
                if not chrome_app.exists():
                    raise Exception(f"Chrome application not found at {chrome_app}")

            # 更新数据库中的 Chrome 路径
            chrome_path = str(chrome_exe)
            await self.set_setting(db, 'chrome_path', chrome_path)
            self.logger.info(f"Chrome path set to: {chrome_path}")

            
            return chrome_path

        except Exception as e:
            self.logger.error(f"Failed to ensure Chrome exists: {str(e)}")
            return None