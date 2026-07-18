import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import AccountSettings from './pages/AccountSettings.vue'
import ClassroomUnifiedPlayerPage from './pages/ClassroomUnifiedPlayerPage.vue'
import DailyPlanPage from './pages/DailyPlanPage.vue'
import DashboardModulePage from './pages/DashboardModulePage.vue'
import DirectionPlanner from './pages/DirectionPlanner.vue'
import KnowledgeUploadPage from './pages/KnowledgeUploadPage.vue'
import KnowledgeStarMapPage from './pages/KnowledgeStarMapPage.vue'
import ProjectHomePage from './pages/ProjectHomePage.vue'
import MethodsWorkspacePage from './pages/MethodsWorkspacePage.vue'
import ResearchToolDetailPage from './pages/ResearchToolDetailPage.vue'
import PracticePaperCreatePage from './pages/PracticePaperCreatePage.vue'
import PracticePaperDetailPage from './pages/PracticePaperDetailPage.vue'
import PracticePaperListPage from './pages/PracticePaperListPage.vue'
import SigninRoute from './pages/SigninRoute.vue'
import SyllabusPage from './pages/SyllabusPage.vue'
import WorkspaceModulePage from './pages/WorkspaceModulePage.vue'

export interface PageMeta {
  title: string
  subtitle: string
  description?: string
  highlights?: string[]
}

export const pageMeta: Record<string, PageMeta> = {
  signin: {
    title: '登录',
    subtitle: '进入智研星链学习工作台',
    description: '登录或注册后继续使用学习项目、学习清单和科研工具。',
    highlights: ['登录注册', '账号验证', '学习工作台']
  },
  directions: {
    title: '探索方向',
    subtitle: '从科研方向生成可持续学习项目',
    description: '围绕一个科研或课程方向完成目标澄清、知识点拆解、资源清单和学习项目初始化。',
    highlights: ['方向理解', '知识点拆解', '学习项目建议']
  },
  projects: {
    title: '项目主页',
    subtitle: '管理方向、目标、阶段和项目进展',
    description: '这里承载已保存的学习项目、当前阶段、待学习课堂和关键产出。',
    highlights: ['项目进度', '阶段产出', '课堂入口']
  },
  syllabus: {
    title: '学习清单',
    subtitle: '项目专属的个性化路径规划与目录总览',
    description: '这里展示当前项目的学习清单，支持生成目录、多模态资源入口和学习状态记录。',
    highlights: ['路径规划', '目录总览', '学习状态']
  },
  classroom: {
    title: 'AI课堂',
    subtitle: '围绕当前学习项完成总结、资源、练习与复盘',
    description: '课堂页承接学习清单中的单个学习项，用结构化学习板块记录学习行为并自动更新进度。',
    highlights: ['课堂学习', '多模态资源', '自动进度']
  },
  'daily-plan': {
    title: '每日计划',
    subtitle: '按日承接学习任务和预生成课堂内容',
    description: '这里将把学习清单拆成每日计划，并支持后台提前生成第二天要学的资料。',
    highlights: ['每日安排', '预生成内容', '继续学习']
  },
  profile: {
    title: '学习画像',
    subtitle: '维护画像条目、画像版本和知识短板',
    description: '画像不再打断主流程，而是作为后台条目持续积累，用于个性化生成内容。',
    highlights: ['画像条目', '知识短板', '版本追踪']
  },
  resources: {
    title: '知识漏斗',
    subtitle: '基于用户知识库动态生成可旋转知识漏斗',
    description: '这里只展示知识漏斗。节点来自用户上传知识库、项目知识点和学习画像的动态聚合，用于把资料证据筛分、收束成科学动态的个性化学习路径。',
    highlights: ['3D知识漏斗', '动态路径', '节点交互']
  },
  'knowledge-upload': {
    title: '知识库',
    subtitle: '上传、解析、管理资料，并基于知识库完成 RAG 问答',
    description: '这里负责知识库资料上传、解析记录、文档内容列表、删除管理和基于资料来源的 RAG 问答。',
    highlights: ['资料上传', '内容管理', 'RAG问答']
  },
  assessment: {
    title: '练习试卷',
    subtitle: '从知识图谱节点生成、保存和作答试卷',
    description: '这里展示历史试卷。新建试卷时从知识点池勾选节点，AI 根据节点生成题目，提交后保存作答、解析和错题。',
    highlights: ['历史试卷', '知识节点出题', '作答解析']
  },
  literature: {
    title: '文献知识库',
    subtitle: '管理论文、笔记、引用和个人知识库',
    description: '这里将支持论文上传、引用管理、阅读笔记和文献关系整理。',
    highlights: ['文献管理', '引用格式', '知识库']
  },
  methods: {
    title: '科研方法',
    subtitle: '学习实验设计、复现、评估和学术规范',
    description: '这里将沉淀科研方法课，包括如何复现论文、设计实验和评价结果。',
    highlights: ['实验设计', '论文复现', '学术规范']
  },
  agents: {
    title: '任务中心',
    subtitle: '查看多智能体编排、生成轨迹和失败状态',
    description: '集中展示 DirectionAgent、SyllabusAgent、ClassroomAgent、VisualizationAgent、EvaluationAgent 等执行轨迹。',
    highlights: ['Agent轨迹', '任务状态', '编排流程']
  },
  settings: {
    title: '系统设置',
    subtitle: '配置模型、API Key、账号资料和系统入口',
    description: '这里维护学生基础信息和当前账号使用的模型服务。模型配置保存后会影响项目规划、课堂生成、RAG 问答和科研工具。',
    highlights: ['模型切换', 'API Key', '账号资料']
  }
}

export const pageRouteNames: Record<string, string> = {
  directions: 'directions',
  projects: 'projects',
  'daily-plan': 'daily-plan',
  profile: 'profile',
  resources: 'resources',
  'knowledge-upload': 'knowledge-upload',
  assessment: 'assessment',
  literature: 'literature',
  methods: 'methods',
  agents: 'agents',
  settings: 'settings'
}

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/directions' },
  { path: '/signin', name: 'signin', component: SigninRoute, meta: { page: 'signin', public: true } },
  { path: '/directions', name: 'directions', component: DirectionPlanner, meta: { page: 'directions' } },
  { path: '/projects', name: 'projects', component: ProjectHomePage, meta: { page: 'projects' } },
  { path: '/projects/:projectId(\\d+)', name: 'project-detail', component: ProjectHomePage, meta: { page: 'projects' } },
  { path: '/projects/:projectId(\\d+)/syllabus', name: 'project-syllabus', component: SyllabusPage, meta: { page: 'syllabus' } },
  { path: '/projects/:projectId(\\d+)/syllabus/items/:itemId(\\d+)/classroom', name: 'project-classroom', component: ClassroomUnifiedPlayerPage, meta: { page: 'classroom' } },
  { path: '/daily-plan', name: 'daily-plan', component: DailyPlanPage, meta: { page: 'daily-plan' } },
  { path: '/projects/:projectId(\\d+)/daily-plan', name: 'project-daily-plan', component: DailyPlanPage, meta: { page: 'daily-plan' } },
  { path: '/profile', name: 'profile', component: WorkspaceModulePage, props: { mode: 'profile' }, meta: { page: 'profile' } },
  { path: '/resources', name: 'resources', component: KnowledgeStarMapPage, meta: { page: 'resources' } },
  { path: '/knowledge-upload', name: 'knowledge-upload', component: KnowledgeUploadPage, meta: { page: 'knowledge-upload' } },
  { path: '/assessment', name: 'assessment', component: PracticePaperListPage, meta: { page: 'assessment' } },
  { path: '/assessment/new', name: 'practice-paper-create', component: PracticePaperCreatePage, meta: { page: 'assessment' } },
  { path: '/assessment/:paperId(\\d+)', name: 'practice-paper-detail', component: PracticePaperDetailPage, meta: { page: 'assessment' } },
  { path: '/literature', name: 'literature', component: WorkspaceModulePage, props: { mode: 'literature' }, meta: { page: 'literature' } },
  { path: '/methods', name: 'methods', component: MethodsWorkspacePage, meta: { page: 'methods' } },
  { path: '/methods/:tool', name: 'research-tool-detail', component: ResearchToolDetailPage, meta: { page: 'methods' } },
  { path: '/agents', name: 'agents', component: DashboardModulePage, meta: { page: 'agents' } },
  { path: '/teacher', redirect: '/settings' },
  { path: '/settings', name: 'settings', component: AccountSettings, meta: { page: 'settings' } },
  { path: '/:pathMatch(.*)*', redirect: '/directions' }
]

export const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  const token = localStorage.getItem('access_token')
  if (token) return true
  return {
    name: 'signin',
    query: { from: to.fullPath }
  }
})
