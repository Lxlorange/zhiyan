import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import AccountSettings from './pages/AccountSettings.vue'
import ClassroomUnifiedPlayerPage from './pages/ClassroomUnifiedPlayerPage.vue'
import DailyPlanPage from './pages/DailyPlanPage.vue'
import DashboardModulePage from './pages/DashboardModulePage.vue'
import DirectionPlanner from './pages/DirectionPlanner.vue'
import ProjectHomePage from './pages/ProjectHomePage.vue'
import MethodsWorkspacePage from './pages/MethodsWorkspacePage.vue'
import SigninRoute from './pages/SigninRoute.vue'
import SyllabusPage from './pages/SyllabusPage.vue'
import WorkspaceModulePage from './pages/WorkspaceModulePage.vue'

export interface PageMeta {
  title: string
  subtitle: string
}

export const pageMeta: Record<string, PageMeta> = {
  signin: { title: '登录', subtitle: '进入学习工作台' },
  directions: { title: '探索方向', subtitle: '从一个方向生成学习项目' },
  projects: { title: '项目主页', subtitle: '查看项目、进度和下一步学习' },
  syllabus: { title: '学习清单', subtitle: '项目专属目录和学习状态' },
  classroom: { title: 'AI 课堂', subtitle: '课件、互动、练习和复盘' },
  'daily-plan': { title: '每日计划', subtitle: '按日推进学习任务' },
  profile: { title: '学习画像', subtitle: '维护画像条目和版本' },
  resources: { title: '资源中心', subtitle: '查看课堂和 Agent 生成资源' },
  tutor: { title: '智能辅导', subtitle: '进入课堂持续追问' },
  assessment: { title: '练习评估', subtitle: '汇总练习、实操和复盘反馈' },
  literature: { title: '文献知识库', subtitle: '管理论文、摘要和引用' },
  writing: { title: '论文写作', subtitle: '选题、综述、润色和答辩' },
  methods: { title: '科研方法', subtitle: '实验设计、复现和学术规范' },
  agents: { title: '任务中心', subtitle: '查看多智能体执行轨迹' },
  settings: { title: '账号设置', subtitle: '维护基础信息' }
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
  { path: '/methods', name: 'methods', component: MethodsWorkspacePage, meta: { page: 'methods' } },
  { path: '/agents', name: 'agents', component: DashboardModulePage, props: { mode: 'agents' }, meta: { page: 'agents' } },
  { path: '/teacher', redirect: '/agents' },
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
