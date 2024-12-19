@echo off
echo Creating frontend project structure...

:: 创建主要目录结构
mkdir src
mkdir public
mkdir src\api
mkdir src\components
mkdir src\features
mkdir src\features\sites
mkdir src\features\tasks
mkdir src\features\statistics
mkdir src\hooks
mkdir src\layouts
mkdir src\store
mkdir src\store\slices
mkdir src\types
mkdir src\utils

:: 创建基础文件
echo // 配置API请求客户端 > src\api\config.ts
echo // 导出所有API请求方法 > src\api\index.ts

:: 创建组件相关文件
echo // 导出所有共享组件 > src\components\index.ts

:: 创建特性模块文件
echo // 站点管理模块 > src\features\sites\index.tsx
echo // 任务管理模块 > src\features\tasks\index.tsx
echo // 统计分析模块 > src\features\statistics\index.tsx

:: 创建布局相关文件
echo // 主布局组件 > src\layouts\MainLayout.tsx
echo // 导出所有布局组件 > src\layouts\index.ts

:: 创建状态管理相关文件
echo // Redux store配置 > src\store\store.ts
echo // Redux Toolkit slices > src\store\slices\index.ts

:: 创建类型定义文件
echo // API相关���型定义 > src\types\api.ts
echo // 通用类型定义 > src\types\common.ts
echo // 站点相关类型定义 > src\types\site.ts
echo // 任务相关类型定义 > src\types\task.ts

:: 创建工具函数文件
echo // 通用工具函数 > src\utils\common.ts
echo // 日期处理工具函数 > src\utils\date.ts
echo // 格式化工具函数 > src\utils\format.ts

:: 创建入口文件
echo // React应用入口文件 > src\App.tsx
echo // 全局样式文件 > src\index.css
echo // 应用入口文件 > src\index.tsx

:: 创建配置文件
echo // TypeScript配置 > tsconfig.json
echo // Vite配置 > vite.config.ts
echo // ESLint配置 > .eslintrc.js
echo // Prettier配置 > .prettierrc
echo // 项目依赖配置 > package.json

echo Frontend project structure created successfully! 