import os
import base64
import time
import aiohttp
import asyncio
import json
from typing import Optional
from pathlib import Path
from datetime import datetime
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..base_handler import BaseCaptchaHandler

class APIHandler(BaseCaptchaHandler):
    """2captcha API验证码处理器"""
    
    def __init__(self, storage_dir: Path):
        super().__init__(storage_dir)
        self.api_key = os.getenv('CAPTCHA_API_KEY', '')
        self.api_url = os.getenv('CAPTCHA_API_URL', 'https://api.2captcha.com')
        self.max_retries = int(os.getenv('CAPTCHA_MAX_RETRIES', '3'))
        self.poll_interval = float(os.getenv('CAPTCHA_POLL_INTERVAL', '5.0'))
        self.timeout = int(os.getenv('CAPTCHA_TIMEOUT', '120'))
        self.logger = logger.bind(handler="2captcha")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        before_sleep=lambda retry_state: logger.info(f"重试第 {retry_state.attempt_number} 次...")
    )
    async def _send_request(self, endpoint: str, data: dict) -> dict:
        """发送API请求"""
        try:
            url = f"{self.api_url}/{endpoint}"
            self.logger.debug(f"发送请求到 {url}")
            self.logger.debug(f"请求数据: {json.dumps(data, indent=2)}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    response.raise_for_status()
                    result = await response.json()
                    self.logger.debug(f"API响应: {json.dumps(result, indent=2)}")
                    return result
                    
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"API请求失败: {str(e)}, 状态码: {e.status}, 响应: {e.message}")
            raise
        except Exception as e:
            self.logger.error(f"API请求出错: {str(e)}")
            raise

    async def _submit_captcha(self, image_data: bytes) -> str:
        """提交验证码到API"""
        self.logger.info("开始提交验证码到2captcha")
        
        # 准备请求数据
        data = {
            "clientKey": self.api_key,
            "task": {
                "type": "ImageToTextTask",
                "body": base64.b64encode(image_data).decode(),
                "phrase": False,
                "case": False,
                "numeric": False,
                "math": False,
                "minLength": 1,
                "maxLength": 10,
                "comment": "PT站点验证码识别"
            },
            "languagePool": "en"
        }
        
        try:
            # 发送请求
            self.logger.debug("发送验证码识别请求...")
            result = await self._send_request('createTask', data)
            
            if result.get('errorId') != 0:
                error_msg = result.get('errorDescription', '未知错误')
                self.logger.error(f"验证码提交失败: {error_msg}")
                raise Exception(f"验证码提交失败: {error_msg}")
            
            task_id = result.get('taskId')
            if not task_id:
                raise Exception("未获取到taskId")
                
            self.logger.info(f"验证码提交成功，任务ID: {task_id}")
            return str(task_id)
            
        except Exception as e:
            self.logger.error(f"验证码提交过程出错: {str(e)}")
            raise

    async def _get_result(self, task_id: str) -> Optional[str]:
        """获取验证码识别结果"""
        start_time = time.time()
        attempt = 0
        
        while True:
            attempt += 1
            elapsed = time.time() - start_time
            
            if elapsed > self.timeout:
                self.logger.error(f"验证码识别超时，已等待 {elapsed:.1f} 秒")
                return None
            
            try:
                # 构建请求数据
                data = {
                    "clientKey": self.api_key,
                    "taskId": int(task_id)
                }
                
                self.logger.debug(f"第 {attempt} 次查询结果，已等待 {elapsed:.1f} 秒")
                result = await self._send_request('getTaskResult', data)
                
                if result.get('errorId') != 0:
                    error_msg = result.get('errorDescription', '未知错误')
                    self.logger.error(f"获取验证码结果失败: {error_msg}")
                    return None
                
                status = result.get('status')
                if status == 'ready':
                    solution = result.get('solution', {})
                    captcha_text = solution.get('text', '').strip()
                    if not captcha_text:
                        self.logger.error("获取到空的验证码文本")
                        return None
                    
                    cost = result.get('cost', '0')
                    self.logger.info(f"验证码识别成功: {captcha_text}, 花费: {cost}")
                    return captcha_text
                    
                elif status == 'processing':
                    self.logger.debug("验证码还未识别完成，等待下次查询...")
                    await asyncio.sleep(self.poll_interval)
                    continue
                    
                else:
                    self.logger.error(f"未知的任务状态: {status}")
                    return None
                    
            except Exception as e:
                self.logger.error(f"查询验证码结果出错: {str(e)}")
                if attempt >= self.max_retries:
                    self.logger.error("已达到最大重试次数，放弃查询")
                    return None
                await asyncio.sleep(self.poll_interval)

    async def handle(self, image_data: bytes, site_id: str) -> Optional[str]:
        """处理验证码"""
        try:
            # 保存验证码图片用于调试
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            image_path = self.storage_dir / f'{site_id}_{timestamp}.png'
            image_path.write_bytes(image_data)
            self.logger.info(f"验证码图片已保存: {image_path}")

            # 提交验证码
            task_id = await self._submit_captcha(image_data)
            if not task_id:
                return None

            # 获取识别结果
            return await self._get_result(task_id)
            
        except Exception as e:
            self.logger.error(f"验证码处理失败: {str(e)}")
            return None

    def cleanup(self):
        """清理资源"""
        # API处理器不需要特别的清理操作
        pass 