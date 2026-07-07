# 智研星链 A3

面向 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”的前后端初始化工程。

## 目录

- `frontend/`: Vue 3 + Vite + TypeScript 前端。
- `backend/`: FastAPI 后端与多智能体/RAG mock 服务。
- `docs/`: 赛题材料和项目计划书。

## 本地启动

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

前端默认请求 `http://localhost:8000/api`。
