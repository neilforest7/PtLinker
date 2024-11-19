@echo off
echo Creating project structure...

:: 创建主目录
mkdir frontend
mkdir crawler
mkdir backend
mkdir docker

:: 前端结构
cd frontend
mkdir public
mkdir src
cd src
mkdir components
cd components
mkdir common
mkdir crawler
mkdir task
mkdir data
cd ..
mkdir hooks
mkdir stores
mkdir services
mkdir types
mkdir utils
cd ..

:: 创建前端基础文件
echo {} > package.json
echo. > src\index.tsx
echo. > src\App.tsx
cd ..

:: 爬虫服务结构
cd crawler
mkdir src
cd src
mkdir crawlers
mkdir handlers
mkdir storage
mkdir utils
mkdir types
cd ..
mkdir storage
cd storage
mkdir datasets
mkdir key_value
cd ..
echo {} > package.json
cd ..

:: 后端结构
cd backend
mkdir app
cd app
mkdir api
mkdir core
mkdir models
mkdir services
mkdir utils

:: API目录
cd api
mkdir v1
mkdir ws
echo. > v1\__init__.py
echo. > ws\__init__.py
cd ..

:: Core目录
cd core
mkdir config
mkdir events
mkdir logging
echo. > __init__.py
cd ..

:: Models目录
cd models
mkdir pydantic
mkdir db
echo. > __init__.py
cd ..

:: Services目录
cd services
mkdir crawler
echo. > __init__.py
echo. > task.py
echo. > data.py
cd ..

cd ..
mkdir tests
cd tests
mkdir unit
mkdir integration
cd ..

:: 创建后端基础文件
echo. > requirements.txt
echo. > app\main.py
cd ..

:: Docker配置
cd docker
mkdir frontend
mkdir crawler
mkdir backend
echo. > frontend\Dockerfile
echo. > crawler\Dockerfile
echo. > backend\Dockerfile
cd ..

:: 创建根目录配置文件
echo. > .gitignore
echo. > docker-compose.yml
echo. > README.md

echo Project structure created successfully!
pause 