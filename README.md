# Claude Manager

Claude Code 托管代理管理后台，支持多用户、多项目、实时状态监控。

## 快速开始

```bash
# 初始化
bash init.sh

# 启动服务
bash start.sh

# 访问
# 前端: http://localhost:3112
# 后端: http://localhost:8112
```

## 停止服务

```bash
# 启动脚本已内置旧进程清理，再次运行 start.sh 即可重启
bash start.sh
```

## 技术栈

- **后端**: FastAPI + uvicorn + SQLite
- **前端**: Vue 3 + Vite
- **头像**: 8x8 像素画生成

## 目录结构

```
backend/          # FastAPI 后端
  api/            # API 路由
  main.py         # 入口
  db.py           # 数据库操作
  generate_avatars.py  # 头像生成脚本
  pyproject.toml  # Python 依赖
frontend/         # Vue 3 前端
  src/
    components/   # 组件
    utils/        # 工具函数
  vite.config.js  # Vite 配置
init.sh           # 初始化脚本
start.sh          # 启动脚本
```
