# 智研星链

智研星链是一个面向高校课程学习与科研训练的多智能体学习平台。系统围绕用户输入、上传资料和已导入知识库生成学习项目、学习清单、每日计划、集成课堂、练习试卷、科研工具与学习画像。

## 工程目录

- `backend/`: FastAPI 后端、PostgreSQL 数据模型、多智能体服务、知识库导入与检索增强链路。
- `frontend/`: Vue 3 + Vite + Element Plus 前端。
- `docs/`: 需求文档、赛题资料和项目说明。

## 本地数据库

后端使用 PostgreSQL 和 pgvector。先准备数据库：

```sql
CREATE DATABASE zhiyan_xinglian;
CREATE USER zhiyan WITH PASSWORD 'zhiyan';
GRANT ALL PRIVILEGES ON DATABASE zhiyan_xinglian TO zhiyan;
\c zhiyan_xinglian
GRANT ALL ON SCHEMA public TO zhiyan;
CREATE EXTENSION IF NOT EXISTS vector;
```

复制并修改后端环境变量：

```powershell
Copy-Item backend\.env.example backend\.env
```

默认连接串：

```text
DATABASE_URL=postgresql+psycopg://zhiyan:zhiyan@localhost:5432/zhiyan_xinglian
```

配置千问兼容接口：

```text
LLM_PROVIDER=qwen
QWEN_API_KEY=你的千问 API Key
QWEN_MODEL=qwen-plus
QWEN_BASE_URL=https://ws-zdgnhxh8fif3r56e.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

未配置 `QWEN_API_KEY` 时，AI 生成接口会直接返回错误；项目不会使用静态预设内容。

## 启动

后端会托管已构建的前端资源。开发时可分别启动，也可只启动后端访问构建产物。

```powershell
cd frontend
npm install
npm run build
```

```powershell
cd ..\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

访问：

- 页面：`http://127.0.0.1:18000`
- API 文档：`http://127.0.0.1:18000/docs`

## 核心链路

`注册/登录 -> 知识库导入 -> 探索方向 -> 构建项目 -> 自动生成学习清单与每日计划 -> 集成课堂学习 -> 练习评估 -> 笔记与行为沉淀画像 -> 画像反哺后续项目生成`

## 主要功能

- 学习项目：通过智能体对话生成项目计划，并构建可管理的学习项目。
- 知识库：上传课件、论文、习题解析等资料，入库后用于检索增强和资源生成。
- 学习清单：按项目目标生成可调整的课程大纲式学习项。
- 每日计划：根据每日学习时长和学习日自动排期，可调整但不直接删除课程。
- 集成课堂：围绕当前学习项生成动态课件、讲解、互动演示、练习和复盘。
- 练习试卷：从知识点池选择节点生成试卷，作答后提供解析和错题沉淀。
- 科研工具：支持文献、写作、方法、实验计划和模拟答辩等科研训练任务。

## 部署

仓库包含 Docker Compose 和 GitHub Actions 部署配置。默认生产部署目录为：

```text
/opt/zhiyan-xinglian/current
```

如服务器实际目录不同，修改 `.github/workflows/deploy.yml` 中的部署路径即可。
