# PT站点爬虫管理系统

## 项目概述
本项目是一个前后端分离的 Web 应用，提供高效的 PT 站点爬虫功能，支持**网页登录、签到、数据统计**等功能。前端使用 **React** 和 **Ant Design** 框架构建，后端使用 **FastAPI** 和 **SQLite** 数据库，爬虫功能则使用 **DrissionPage** 实现。项目设计为无用户认证模式，简化配置，便于用户直接使用。

## 技术栈

### 前端
- **语言**: TypeScript
- **框架**: React 18
- **UI 组件库**: Ant Design 5.0
- **状态管理**: Redux
- **HTTP 请求**: Axios
- **构建工具**: Vite
- **代码规范**: ESLint + Prettier

### 后端服务 (Python)
- **框架**: FastAPI
- **数据库**: SQLite + SQLAlchemy
- **数据验证**: Pydantic v2
- **数据迁移**: Alembic
- **爬虫框架**: DrissionPage
- **验证码处理**:
  - ddddocr (本地识别)
  - 2captcha (在线识别)
- **日志管理**: loguru

## 系统架构

### 两层架构
1. **前端层**: React单页应用
2. **后端层**: FastAPI RESTful服务 + 爬虫服务

### 服务通信
- 前端 <-> 后端: RESTful API + WebSocket

## 项目结构
```
PtLinker
├── app                      # 后端应用
│   ├── api                 # API路由
│   │   └── v1             # API版本1
│   ├── core               # 核心功能
│   ├── handlers          # 请求处理器
│   ├── models            # 数据模型
│   ├── schemas           # 数据验证模式
│   ├── services          # 业务服务
│   │   ├── captcha      # 验证码服务
│   │   ├── crawler      # 爬虫服务
│   │   ├── managers     # 管理器
│   │   └── sites        # 站点配置
│   │       └── implementations  # 站点实现
│   ├── storage           # 存储相关
│   └── utils             # 工具函数
├── frontend               # 前端应用
│   ├── public            # 静态资源
│   ├── src
│   │   ├── api/                # API 请求
│   │   ├── components/         # 共享组件
│   │   ├── features/          # 功能模块
│   │   │   ├── sites/         # 站点管理
│   │   │   ├── tasks/         # 任务管理
│   │   │   └── statistics/    # 统计分析
│   │   ├── hooks/             # 自定义 Hooks
│   │   ├── layouts/           # 布局组件
│   │   ├── store/             # Redux 状态
│   │   │   ├── slices/        # Redux Toolkit slices
│   │   │   └── store.ts       # Redux store 配置
│   │   ├── types/             # TypeScript 类型定义
│   │   └── utils/             # 工具函数
└── docker                 # Docker配置
    ├── backend           # 后端Docker配置
    └── frontend          # 前端Docker配置
```

## 功能特性

### 1. 站点管理
- 支持多个PT站点配置
- 站点状态监控
- 配置在线编辑
- 站点测试功能

### 2. 任务管理
- 定时任务支持
- 任务优先级
- 失败重试机制
- 任务状态追踪

### 3. 数据采集
- 用户数据采集
- 做种数据统计
- 流量统计分析
- 数据导出功能

### 4. 验证码处理
- 本地识别(ddddocr)
- 在线识别(2captcha)
- 手动识别支持
- 验证码识别训练

## 站点配置

### 配置结构
每个站点的配置包含以下主要部分:
- **基础信息**: site_id, site_url
- **登录配置**: 包含登录表单、验证码等配置
- **数据提取规则**: 用于提取用户信息、做种信息等
- **签到配置**: 签到按钮和URL配置

### 支持站点
目前支持的PT站点包括:
- HDAtoms
- HDHome 
- Ourbits
- U2
- FRDS
- Haidan
- HDFans
- UBITS
- 等多个主流PT站点

## 部署说明

### 开发环境

1. 前端服务
```bash
cd frontend
npm install
npm run dev
```

2. 后端服务
```bash
cd app
python -m venv venv
source venv/bin/activate  # Windows使用: .\venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 生产环境
使用Docker Compose进行部署:
```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d
```

## 配置说明

### 环境变量
```env
# API服务配置
API_PORT=8000
DATABASE_URL=sqlite:///ptlinker.db

# 爬虫配置
CRAWLER_MAX_CONCURRENCY=8
FRESH_LOGIN=false
LOGIN_MAX_RETRY=3

# 验证码配置
CAPTCHA_API_KEY=your_api_key
CAPTCHA_API_URL=https://2captcha.com/in.php
```

### 浏览器配置
```python
browser_config = {
    "headless": True,
    "timeout": 20,
    "stealth": True,
    "auto_close_pages": True
}
```

## 开发指南

### 添加新站点
1. 在 `app/services/sites/implementations` 创建站点配置文件
2. 实现必要的数据提取规则
3. 注册站点到站点管理器
4. 测试站点功能

### 代码规范
- 使用 Black 格式化 Python 代码
- 使用 Prettier 格式化前端代码
- 遵循 PEP 8 规范
- 编写单元测试

## 贡献指南
1. Fork 项目
2. 创建特性分支
3. 提交变更
4. 推送到分支
5. 创建 Pull Request

## 许可证
MIT License
