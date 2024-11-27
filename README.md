# 项目设计文档

## 项目概述
本项目旨在构建一个前后端分离的 Web 应用，提供高效的网页爬虫功能，以供**网页登录、签到、数据统计**。前端使用 **React** 和 **Ant Design** 框架构建，后端使用 **SQLite** 数据库存储数据，爬虫功能则使用 **Crawlee v3 for Python** 和 **Playwright** 实现。项目设计为无用户认证和登录，简化配置，便于用户直接使用。

## 技术栈

### 前端
- **语言**: TypeScript
- **框架**: React
- **UI 组件库**: Ant Design
- **状态管理**: Zustand
- **HTTP 请求库**: Axios
- **样式管理**: CSS Modules 或 Styled Components

### 爬虫服务 (Python)
- **运行环境**: Python 3.10+
- **爬虫框架**: 
  - Crawlee v3 for Python (核心爬虫引擎)
  - Playwright for Python (浏览器自动化)
  - DrissionPage (Cloudflare绕过方案)
- **数据验证**: Pydantic v2
- **日志管理**: loguru
- **环境配置**: python-dotenv
- **数据存储**: 
  - Crawlee Dataset
  - Crawlee KeyValueStore
  - Crawlee RequestQueue

### 后端服务 (Python)
- **框架**: FastAPI
- **数据库**: SQLite + SQLAlchemy
- **数据验证**: Pydantic v2
- **数据迁移**: Alembic

## 系统架构

### 三层架构
1. **前端层**: React应用
2. **爬虫服务层**: Python + Crawlee + Playwright + DrissionPage
3. **API服务层**: Python FastAPI

### 服务通信
- 前端 <-> API服务: RESTful API + WebSocket
- API服务 <-> 爬虫服务: 消息队列 + 文件系统
- 爬虫服务 -> 数据库: 通过API服务中转

## 项目结构
```
project/
├── frontend/                # 前端项目
│   ├── public/              # 静态资源
│   └── src/
│       ├── components/      # React组件
│       │   ├── common/      # 通用组件
│       │   ├── crawler/     # 爬虫相关组件
│       │   ├── task/       # 任务管理组件
│       │   └── data/       # 数据展示组件
│       ├── hooks/          # 自定义Hooks
│       ├── stores/         # Zustand状态管理
│       ├── services/       # API服务
│       ├── types/          # TypeScript类型定义
│       └── utils/          # 工具函数
│
├── crawler_py/                 # 爬虫服务 (Python)
│   ├── src/
│   │   ├── crawlers/       # Crawlee爬虫实现
│   │   │   ├── base/      # 基础爬虫类
│   │   │   └── sites/     # 站点特定爬虫
│   │   ├── extractors/    # 数据提取器
│   │   ├── handlers/      # 请求处理器
│   │   │   ├── login.py   # 登录处理
│   │   │   └── captcha.py # 验证码处理
│   │   ├── models/        # 数据模型(Pydantic)
│   │   ├── storage/       # 存储管理
│   │   └── utils/         # 工具函数
│   ├── storage/            # Crawlee存储目录
│   │   ├── datasets/      # 数据集存储
│   │   ├── key_value/     # KV存储
│   │   └── request_queues/ # 请求队列
│   └── config/            # 配置文件
│
├── backend/                 # API服务 (Python)
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心功能
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   └── utils/          # 工具函数
│   └── requirements.txt
│
└── docker/                 # Docker配置
    ├── frontend/
    ├── crawler/           # 爬虫服务Docker配置
    └── backend/
```

## 部署架构

### 开发环境
1. 前端服务
```bash
cd frontend && npm install && npm start
```

2. 爬虫服务
```bash
cd crawler && npm install && npm start
```

3. API服务
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 生产环境
使用Docker Compose管理三个服务：
```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "80:80"
    
  crawler:
    build: ./crawler
    volumes:
      - crawler_storage:/app/storage
    
  backend:
    build: ./backend
    volumes:
      - db_data:/app/data
```

## 爬虫系统设计

### 1. 爬虫核心功能

#### 1.1 基础爬取能力
- **页面处理**
  - 基于Crawlee的统一爬取接口
  - Playwright自动化支持
  - DrissionPage备选方案
  - 验证码识别集成

- **数据提取**
  - 基于Pydantic的数据模型
  - CSS选择器提取
  - XPath提取
  - 正则表达式匹配
  - 自定义Python提取器

- **请求控制**
  - Crawlee内置重试机制
  - 自定义请求头
  - 内置代理支持
  - 自动请求限速
  - 并发数控制

#### 1.2 会话管理
- **登录态维护**
  - Crawlee Session Pool
  - Cookie持久化
  - 会话状态检测
  - 自动登录重试

- **会话池配置**
  - Crawlee内置会话管理
  - 会话最大使用次数
  - 会话存活时间
  - 错误分数机制

#### 1.3 任务调度
- **队列管理**
  - Crawlee RequestQueue
  - 内置优先级队列
  - 失败重试队列
  - 定时任务支持

- **资源控制**
  - 内置内存管理
  - CPU使用限制
  - 网络带宽控制
  - 存储空间管理

### 2. 数据处理流程

#### 2.1 数据采集
- **数据源适配**
  - HTML页面
  - AJAX请求
  - WebSocket数据
  - 文件下载

- **数据清洗**
  - Pydantic模型验证
  - 自动类型转换
  - 数据规范化
  - 字段提取和转换

#### 2.2 数据存储
- **即时存储**
  - Crawlee Dataset API
  - KeyValueStore API
  - 内存缓存
  - 自动去重

- **持久化存储**
  - SQLite + SQLAlchemy
  - 文件系统存储
  - 定期数据同步
  - 数据备份机制

### 3. 监控与告警

#### 3.1 性能监控
- **资源监控**
  - CPU使用率
  - 内存占用
  - 磁盘使用情况
  - 网络流量

- **爬虫指标**
  - 请求成功率
  - 平均响应时间
  - 数据采集速率
  - 任务完成率

#### 3.2 异常处理
- **错误类型**
  - 网络错误
  - 解析错误
  - 验证码错误
  - 登录失败
  - 反爬封锁

- **处理策略**
  - 自动重试机制
  - 错误日志记录
  - 告警通知
  - 降级处理

### 4. 扩展能力

#### 4.1 反爬处理
- **基础对抗**
  - User-Agent轮换
  - Cookie管理
  - 请求延迟
  - 代理IP池

- **高级对抗**
  - 浏览器指纹伪装
  - WebDriver隐藏
  - Canvas指纹处理
  - JavaScript混淆绕过

#### 4.2 定制化能力
- **规则配置**
  - 可视化规则编辑
  - 规则模板管理
  - 规则版本控制
  - 规则测试验证

- **中间件扩展**
  - 请求处理中间件
  - 响应处理中间件
  - 数据处理中间件
  - 存储处理中间件

### 5. 安全与合规

#### 5.1 访问控制
- 请求频率限制
- 并发数控制
- IP访问限制
- 资源使用限制

#### 5.2 数据安全
- 敏感数据脱敏
- 数据加密存储
- 访问日志记录
- 数据备份策略
