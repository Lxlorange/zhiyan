# 智研星链 A3

面向 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”的一体化演示工程。

## 目录

- `backend/`: FastAPI 后端、多智能体链路和内置轻量前端。
  - `backend/app/api/`: API 路由，按课程、工作流、教师端拆分。
  - `backend/app/services/`: 画像、诊断、路径、资源、辅导、评估等业务服务。
  - `backend/app/web/`: FastAPI 托管的轻量前端。
- `frontend/`: 可选的 Vue 3 + Vite 前端草稿；当前主演示不依赖它。
- `docs/`: 赛题材料和项目计划书。

## 本地启动

本项目后端使用 PostgreSQL。先准备数据库：

```sql
CREATE DATABASE zhiyan_a3;
CREATE USER zhiyan WITH PASSWORD 'zhiyan';
GRANT ALL PRIVILEGES ON DATABASE zhiyan_a3 TO zhiyan;
\c zhiyan_a3
GRANT ALL ON SCHEMA public TO zhiyan;
```

如你的 PostgreSQL 用户、密码或端口不同，复制 `backend/.env.example` 为 `backend/.env` 后修改 `DATABASE_URL`：

```powershell
Copy-Item backend\.env.example backend\.env
```

默认连接串：

```text
DATABASE_URL=postgresql+psycopg://zhiyan:zhiyan@localhost:5432/zhiyan_a3
```

配置千问 API Key 后，画像、诊断、路径、资源、题目、辅导和评估会走真实 AI 生成：

```text
LLM_PROVIDER=qwen
QWEN_API_KEY=你的千问DashScope API Key
QWEN_MODEL=qwen-plus
QWEN_BASE_URL=https://ws-1ulzsdw0gslyucjg.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

如果未配置 `QWEN_API_KEY`，AI 链路接口会返回 `503`，提示缺少千问 API Key。
运行时固定读取 `backend/.env`，不是 `.env.example`；如果页面弹窗显示 `503`，优先检查 `backend/.env` 中的 `QWEN_API_KEY`、`LLM_PROVIDER` 和 `QWEN_BASE_URL`。

推荐一体化启动：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

然后访问：

- 页面：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`

也可以在项目根目录启动：

```powershell
python run.py
```

## 当前已实现链路

`注册/登录 -> 学生对话画像 -> 诊断知识短板 -> 规划学习路径 -> 多 Agent 生成资源 -> 智能辅导 -> 练习评估 -> 更新画像`

核心接口：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/workflow/start`
- `GET /api/workflow/{session_id}`
- `POST /api/tutor`
- `POST /api/assessments`
- `GET /api/course/map`
- `GET /api/teacher/dashboard`

详细操作和预期返回见：

- `docs/用户操作与预期返回.md`
