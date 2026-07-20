# 智研星链

智研星链是一个面向高校课程学习与科研训练的多智能体个性化学习平台。系统将用户目标、课程资料、文献资料、知识库证据和学习画像串联起来，自动生成学习项目、学习清单、每日 TODO、AI 课堂、互动演示、练习评估与复盘画像。

我们通过构建多智能体，实现了“上传资料 -> 知识抽取 -> 路径规划 -> 课堂生成 -> 学习行为沉淀 -> 画像反哺下一轮生成”的可演示、可追踪、可管理的闭环。

## 核心亮点

- 知识库驱动：支持上传 PPT、PDF、Word 等课程资料，自动解析、清洗、切分、向量化，并沉淀为可检索知识库。
- 知识漏斗：将 RAG 资料收束为更少、更核心的知识点，按大类染色，形成上大下小的漏斗式知识结构与路径推荐。
- RAG 防幻觉：生成前先检索证据，采用向量相似度、关键词匹配和来源权重综合排序；生成结果尽量绑定来源引用，缺少证据时降低断言强度。
- 个性化学习项目：从用户探索方向出发，结合知识库和学习画像动态规划项目、阶段和学习清单。
- 每日计划 TODO：跨项目汇总所有学习项，按日期分组，支持交叉学习、调整顺序、移动日期和继续学习。
- AI 集成课堂：围绕单个学习项生成课件页、知识卡、测验、互动演示、阅读材料和复盘入口。
- 互动可视化：支持算法流程、状态流转、数据流和 3D/动态演示，让抽象知识更适合现场展示。
- 学习画像闭环：用户可手动新增、修改、删除画像条目；课堂复盘和完成记录会分条写入画像，用于后续路径与内容生成。
- 科研工具箱：提供文献管理、科研方法、写作辅助和模拟答辩等轻量工具链。

## 技术栈

### 前端

- Vue 3
- Vite
- TypeScript
- Element Plus
- ECharts / Canvas / KaTeX / Mermaid

### 后端

- FastAPI
- SQLAlchemy
- PostgreSQL
- pgvector
- python-pptx / python-docx / pypdf / PyMuPDF
- Qwen 兼容 OpenAI Chat Completions 接口

### 数据与智能体

- RAG 文档切分、embedding、检索增强生成
- JSON 结构化生成与自动修复
- 学习项目规划智能体
- 学习清单智能体
- 课堂生成智能体
- 可视化演示生成智能体
- 学习画像更新智能体

## 工程目录

```text
A3/
├─ backend/                 # FastAPI 后端服务
│  ├─ app/
│  │  ├─ api/               # API 路由
│  │  ├─ core/              # 配置、数据库、鉴权
│  │  ├─ models/            # SQLAlchemy 数据模型
│  │  ├─ services/          # 项目规划、RAG、课堂、画像等核心逻辑
│  │  └─ schemas.py         # Pydantic 数据结构
│  ├─ requirements.txt
│  └─ run.py
├─ frontend/                # Vue 3 前端
│  ├─ src/
│  │  ├─ components/        # 通用组件与知识图谱组件
│  │  ├─ pages/             # 页面模块
│  │  ├─ services/          # API 客户端、公式渲染
│  │  └─ router.ts
│  └─ package.json
├─ docs/                    # 项目资料与说明文档
├─ scripts/                 # 辅助脚本
├─ uploaded_knowledge/      # 本地知识库上传文件目录
├─ docker-compose.dev.yml   # 本地 PostgreSQL + pgvector
├─ docker-compose.prod.yml  # 生产部署编排
└─ README.md
```

## 在线演示

已部署的在线演示地址：

[http://121.41.118.240/directions](http://121.41.118.240/directions)

## 本地运行


### 1. 准备数据库

推荐直接使用仓库提供的开发数据库：

```powershell
docker compose -f docker-compose.dev.yml up -d
```

也可以手动创建数据库：

```sql
CREATE DATABASE zhiyan_a3;
CREATE USER zhiyan WITH PASSWORD 'zhiyan';
GRANT ALL PRIVILEGES ON DATABASE zhiyan_a3 TO zhiyan;
\c zhiyan_a3
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL ON SCHEMA public TO zhiyan;
```

### 2. 配置后端环境变量

```powershell
Copy-Item backend\.env.example backend\.env
```

重点配置项：

```text
DATABASE_URL=postgresql+psycopg://zhiyan:zhiyan@127.0.0.1:15432/zhiyan_a3
LLM_PROVIDER=qwen
QWEN_API_KEY=模型 API Key
QWEN_MODEL=qwen-plus
QWEN_BASE_URL=https://ws-zdgnhxh8fif3r56e.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
KNOWLEDGE_EMBEDDING_MODEL=text-embedding-v3
KNOWLEDGE_EMBEDDING_DIM=1024
LOCAL_OCR_ENGINE=tesseract
TESSERACT_CMD=%APP_HOME%\Tesseract-OCR\tesseract.exe
LIBREOFFICE_PATH=%APP_HOME%\LibreOffice\program\soffice.exe
```

### 3. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

默认地址：

- 后端服务：`http://127.0.0.1:18000`
- API 文档：`http://127.0.0.1:18000/docs`

### 4. 启动前端

开发模式：

```powershell
cd frontend
npm install
npm run dev
```

默认前端地址：

```text
http://127.0.0.1:5173
```

生产构建：

```powershell
cd frontend
npm run build
```

后端会托管 `frontend/dist` 中的构建产物，因此构建后也可以直接访问：

```text
http://127.0.0.1:18000
```

## 主要页面

- 探索方向：输入研究/课程目标，结合用户画像和知识库生成学习项目。
- 项目主页：查看项目进度、阶段目标、最近课堂和后续建议。
- 学习清单：管理项目下的课程式学习项，可调整、生成和进入课堂。
- 每日计划：全局 TODO list，跨多个项目按日期聚合学习任务，支持顺序调整。
- AI 课堂：生成结构化课件、知识卡、测验、互动演示、阅读资源和复盘。
- 知识库：上传资料、查看导入记录、管理文档、进行 RAG 问答。
- 知识漏斗：以漏斗和动态图形式查看知识点、分类、前置关系和学习路径。
- 学习画像：维护个性化画像条目，支持手动新增、修改、删除。
- 练习试卷：从知识点生成练习试卷并保存作答解析。
- 科研工具箱：文献、写作、方法和答辩等科研训练入口。
