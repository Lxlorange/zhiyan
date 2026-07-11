import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import AccountSettings from './pages/AccountSettings.vue'
import ClassroomUnifiedPlayerPage from './pages/ClassroomUnifiedPlayerPage.vue'
import DailyPlanPage from './pages/DailyPlanPage.vue'
import DashboardModulePage from './pages/DashboardModulePage.vue'
import DirectionPlanner from './pages/DirectionPlanner.vue'
import ProjectHomePage from './pages/ProjectHomePage.vue'
import SigninRoute from './pages/SigninRoute.vue'
import SyllabusPage from './pages/SyllabusPage.vue'
import WorkspaceModulePage from './pages/WorkspaceModulePage.vue'

export interface PageMeta {
  title: string
  subtitle: string
  description: string
  highlights: string[]
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
    title: '资源中心',
    subtitle: '多 Agent 个性化资源生成与管理',
    description: '这里将集中管理文档、题库、思维导图、视频脚本、实操案例等资源。',
    highlights: ['资源卡片', '多模态内容', '生成记录']
  },
  tutor: {
    title: '智能辅导',
    subtitle: '围绕当前课堂的连续对话式辅导',
    description: '这里将支持课堂内持续对话、例题讲解、可视化演示和引导式提问。',
    highlights: ['持续对话', '例题讲解', '引导追问']
  },
  assessment: {
    title: '练习评估',
    subtitle: '练习反馈、掌握度评估和画像更新',
    description: '这里将记录答题、评分、薄弱点更新和后续资源推荐策略。',
    highlights: ['答题记录', '掌握度评估', '画像更新']
  },
  literature: {
    title: '文献知识库',
    subtitle: '管理论文、笔记、引用和个人知识库',
    description: '这里将支持论文上传、引用管理、阅读笔记和文献关系整理。',
    highlights: ['文献管理', '引用格式', '知识库']
  },
  writing: {
    title: '论文写作',
    subtitle: '论文修改、格式规范、综述和引用辅助',
    description: '这里将提供论文润色、结构诊断、格式规范和综述写作辅助。',
    highlights: ['论文修改', '格式检查', '综述辅助']
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
  teacher: {
    title: '教师驾驶舱',
    subtitle: '查看班级短板、资源使用和教学建议',
    description: '为教师或课程管理员提供方向分布、短板聚合、资源统计和高风险学生提示。',
    highlights: ['班级短板', '资源统计', '教学建议']
  },
  settings: {
    title: '账号设置',
    subtitle: '管理头像、姓名、学校专业和简介',
    description: '这里维护学生基础信息，供顶栏展示和后续个性化画像使用。',
    highlights: ['基础信息', '头像资料', '身份上下文']
  }
}

export const pageRouteNames: Record<string, string> = {
  directions: 'directions',
  projects: 'projects',
  'daily-plan': 'daily-plan',
  profile: 'profile',
  resources: 'resources',
  tutor: 'tutor',
  assessment: 'assessment',
  literature: 'literature',
  writing: 'writing',
  methods: 'methods',
  agents: 'agents',
  teacher: 'teacher',
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
  { path: '/resources', name: 'resources', component: WorkspaceModulePage, props: { mode: 'resources' }, meta: { page: 'resources' } },
  { path: '/tutor', name: 'tutor', component: WorkspaceModulePage, props: { mode: 'tutor' }, meta: { page: 'tutor' } },
  { path: '/assessment', name: 'assessment', component: WorkspaceModulePage, props: { mode: 'assessment' }, meta: { page: 'assessment' } },
  { path: '/literature', name: 'literature', component: WorkspaceModulePage, props: { mode: 'literature' }, meta: { page: 'literature' } },
  { path: '/writing', name: 'writing', component: WorkspaceModulePage, props: { mode: 'writing' }, meta: { page: 'writing' } },
  { path: '/methods', name: 'methods', component: WorkspaceModulePage, props: { mode: 'methods' }, meta: { page: 'methods' } },
  { path: '/agents', name: 'agents', component: DashboardModulePage, props: { mode: 'agents' }, meta: { page: 'agents' } },
  { path: '/teacher', name: 'teacher', component: DashboardModulePage, props: { mode: 'teacher' }, meta: { page: 'teacher' } },
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
