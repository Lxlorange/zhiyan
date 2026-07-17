<template>
  <div class="page classroom-page classroom-unified-page" :class="{ 'deck-focus-mode': isDeckFocusMode }">
    <section class="page-hero classroom-hero">
      <div>
        <p class="eyebrow">AI Classroom</p>
        <h2>{{ currentItem?.title || 'AI 课堂' }}</h2>
      </div>
      <div class="classroom-hero-actions">
        <el-button @click="goBackToSyllabus">返回学习清单</el-button>
        <el-tag v-if="currentItem" :type="statusType(currentItem.status)">{{ statusLabel(currentItem.status) }}</el-tag>
      </div>
    </section>

    <el-empty v-if="!projectId || !itemId" description="请从项目学习清单进入课堂。" />
    <section v-else-if="loading" class="panel-like classroom-loading">正在加载课堂...</section>
    <el-empty v-else-if="!currentItem || !classroom" description="没有找到当前课堂，请返回学习清单重新进入。" />

    <section v-else class="unified-classroom" :class="{ 'deck-focus-mode': isDeckFocusMode }">
      <aside v-if="!isDeckFocusMode" class="unified-sidebar panel-like">
        <div class="classroom-mini-card">
          <span>学习进度</span>
          <strong>{{ completedGateCount }}/4</strong>
          <el-progress :percentage="gateProgress" :stroke-width="10" />
        </div>

        <nav class="classroom-gates" aria-label="课堂闸门">
          <button
            v-for="gate in gates"
            :key="gate.key"
            type="button"
            :class="{ active: activeGate === gate.key, done: gate.done }"
            @click="handleGateSelect(gate.key)"
          >
            <strong>{{ gate.title }}</strong>
            <span>{{ gate.done ? '已完成' : gate.kind }}</span>
          </button>
        </nav>

        <section class="classroom-context-stack">
          <div class="classroom-mini-card">
            <span>知识点</span>
            <div class="classroom-tags">
              <el-tag v-for="point in currentItem.knowledge_points" :key="point" effect="plain">{{ point }}</el-tag>
            </div>
          </div>
          <div class="classroom-mini-card">
            <span>引导问题</span>
            <button v-for="question in guidingQuestions" :key="question.prompt" type="button" @click="askGuidingQuestion(question.prompt)">
              {{ question.prompt }}
            </button>
          </div>
          <div class="classroom-mini-card">
            <span>最近反馈</span>
            <p>{{ latestFeedback || '暂无提交反馈。' }}</p>
          </div>
        </section>

        <section class="classroom-chat">
          <header>
            <strong>课堂追问</strong>
            <el-tag size="small" effect="plain">DialogueAgent</el-tag>
          </header>
          <div class="classroom-chat-log">
            <article
              v-for="message in dialogueMessages"
              :key="`${message.created_at}-${message.role}-${message.content.slice(0, 16)}`"
              :class="message.role"
            >
              <span>{{ message.role === 'user' ? '我' : 'AI 助教' }}</span>
              <p>{{ message.content }}</p>
            </article>
            <p v-if="!dialogueMessages.length" class="empty-chat">生成课堂后可以继续追问。</p>
          </div>
          <div class="quick-actions">
            <button v-for="action in quickActions" :key="action" type="button" @click="sendQuickAction(action)">
              {{ action }}
            </button>
          </div>
          <el-input v-model="chatMessage" type="textarea" :rows="3" placeholder="追问概念、要求举例、让 AI 出题或联系科研方向..." />
          <el-button type="primary" :loading="sendingDialogue" :disabled="!pptPackage || !chatMessage.trim()" @click="handleSendDialogue">
            发送
          </el-button>
        </section>
      </aside>

      <main class="unified-stage panel-like">
        <header class="classroom-stage-head">
          <div>
            <span>{{ activeGateMeta.kind }}</span>
            <h3>{{ activeGateMeta.title }}</h3>
          </div>
          <el-tag :type="activeGateMeta.done ? 'success' : 'warning'" effect="plain">
            {{ activeGateMeta.done ? '已通过' : '待完成' }}
          </el-tag>
        </header>

        <Transition name="panel-swap" mode="out-in">
          <section v-if="activeGate === 'ppt'" key="ppt" class="classroom-pane">
            <Transition name="panel-swap" mode="out-in">
              <div v-if="!pptPackage" key="ppt-preparing" class="classroom-generate classroom-preparing-card">
                <span class="classroom-preparing-dot" aria-hidden="true" />
                <h4>{{ classroomGenerationTitle }}</h4>
                <p>{{ classroomGenerationMessage }}</p>
                <el-progress :percentage="classroomGenerationProgress" :indeterminate="isClassroomGenerating" :stroke-width="10" />
                <p v-if="classroom?.generation_error" class="classroom-error-text">{{ classroom.generation_error }}</p>
                <div class="classroom-action-row">
                  <el-button @click="goBackToSyllabus">返回学习清单</el-button>
                  <el-button
                    v-if="classroom?.status === 'failed'"
                    type="primary"
                    :loading="requestingPptGeneration"
                    @click="ensurePptGeneration(true)"
                  >
                    重新生成
                  </el-button>
                </div>
              </div>

              <section v-else key="lesson-player" class="lesson-player course-learning-shell">
                <section class="om-classroom-player" :class="{ 'panel-open': Boolean(activeAssistantTab) }">
                  <header class="om-player-toolbar">
                    <div class="om-lesson-title">
                      <span>Lesson Deck</span>
                      <strong>{{ currentSlide?.title || pptPackage?.title }}</strong>
                    </div>
                    <div class="om-player-actions">
                      <el-button v-if="pptResource" @click="downloadPpt">下载 PPT</el-button>
                      <el-button type="success" :disabled="!allSlidesViewed || classroom?.slides_completed" @click="handleCompleteSlides">
                        {{ classroom?.slides_completed ? '课件已完成' : `完成课件 ${slidesVisitedCount}/${slideList.length}` }}
                      </el-button>
                    </div>
                  </header>

                  <div class="om-workspace">
                    <main class="om-stage-wrap">
                      <section class="om-slide-stage" :class="`deck-layout-${currentSlideLayout}`">
                        <div class="om-slide-canvas">
                          <div class="om-slide-meta">
                            <span>Slide {{ activeSlideIndex + 1 }} / {{ slideList.length }}</span>
                            <span>{{ currentSlideLayoutLabel }}</span>
                          </div>

                          <div class="om-slide-title">
                            <h4>{{ currentSlide?.title }}</h4>
                            <div class="om-slide-pills">
                              <span v-for="point in currentSlideKnowledgePoints" :key="point">{{ point }}</span>
                            </div>
                          </div>

                          <div class="om-slide-body">
                            <section class="om-slide-main">
                              <p v-if="currentSlide?.visual_hint" class="om-visual-direction">{{ currentSlide.visual_hint }}</p>
                              <ul>
                                <li v-for="bullet in currentSlide?.bullets || []" :key="bullet">{{ bullet }}</li>
                              </ul>
                            </section>

                            <section class="om-insight-panel">
                              <article v-for="block in currentSlideVisualBlocks.slice(0, 3)" :key="`${block.type}-${block.title}`">
                                <span>{{ visualBlockLabel(block.type) }}</span>
                                <strong>{{ block.title }}</strong>
                                <p>{{ block.content }}</p>
                              </article>
                            </section>
                          </div>

                          <footer class="om-slide-footer">
                            <p v-if="currentSlideTakeaways.length">{{ currentSlideTakeaways.slice(0, 3).join(' · ') }}</p>
                            <p v-else-if="currentSlideSidePanel">{{ currentSlideSidePanel.items.slice(0, 3).join(' · ') }}</p>
                          </footer>
                        </div>
                      </section>

                      <div class="om-slide-controls">
                        <el-button :disabled="activeSlideIndex <= 0" @click="goToSlide(activeSlideIndex - 1)">上一页</el-button>
                        <div class="om-progress-line"><span :style="{ width: `${slideReadPercent}%` }" /></div>
                        <strong>{{ slideReadPercent }}%</strong>
                        <el-button :disabled="activeSlideIndex >= slideList.length - 1" @click="goToSlide(activeSlideIndex + 1)">下一页</el-button>
                      </div>

                      <div class="om-slide-strip" aria-label="课件页导航">
                        <button
                          v-for="(slide, index) in slideList"
                          :key="`${slide.title}-${index}`"
                          type="button"
                          :class="{ active: activeSlideIndex === index, viewed: visitedSlideIndices.has(index) }"
                          @click="goToSlide(index)"
                        >
                          <small>{{ index + 1 }}</small>
                          <span>{{ slide.title }}</span>
                        </button>
                      </div>
                    </main>

                    <aside class="om-assistant-dock" :class="{ open: Boolean(activeAssistantTab) }">
                      <nav class="om-assistant-tabs" aria-label="课堂工具">
                        <button
                          v-for="tab in assistantTabs"
                          :key="tab.key"
                          type="button"
                          :class="{ active: activeAssistantTab === tab.key }"
                          @click="toggleAssistantTab(tab.key)"
                        >
                          {{ tab.label }}
                        </button>
                      </nav>

                      <Transition name="panel-swap" mode="out-in">
                        <section v-if="activeAssistantTab === 'lecture'" key="lecture" class="om-tool-panel">
                          <header>
                            <strong>当前页讲解</strong>
                            <div class="voice-actions">
                              <el-button type="primary" :disabled="!voiceText" @click="toggleLectureVoice">
                                {{ isSpeaking ? '暂停' : '播放' }}
                              </el-button>
                              <el-button :disabled="!voiceText" @click="stopVoice">停止</el-button>
                            </div>
                          </header>
                          <p class="om-lecture-text">{{ currentSlideExplanation }}</p>
                          <div v-if="showLectureSubtitle" class="lecture-subtitle">{{ voiceText }}</div>
                          <div class="om-insight-list">
                            <article v-if="currentSlide?.example"><span>案例</span><p>{{ currentSlide.example }}</p></article>
                            <article v-if="currentSlide?.misconception"><span>易错点</span><p>{{ currentSlide.misconception }}</p></article>
                            <article v-if="currentSlide?.interaction_prompt"><span>互动问题</span><p>{{ currentSlide.interaction_prompt }}</p></article>
                          </div>
                        </section>

                        <section v-else-if="activeAssistantTab === 'interactive'" key="interactive" class="om-tool-panel om-visual-panel">
                          <div class="visual-kind-row">
                            <el-select v-model="visualizationKind" size="small" class="visual-kind-select" :disabled="generatingVisualization">
                              <el-option v-for="option in visualizationKindOptions" :key="option.value" :label="option.label" :value="option.value" />
                            </el-select>
                          </div>
                          <header>
                            <strong>互动演示</strong>
                            <el-button type="primary" :loading="generatingVisualization" :disabled="!pptPackage" @click="handleGenerateVisualization">
                              {{ visualizationResource ? '重新生成' : '生成演示' }}
                            </el-button>
                          </header>
                          <iframe v-if="visualizationUrl" :src="visualizationUrl" title="课堂动态演示" />
                          <div v-else class="om-empty-tool">
                            <p>根据当前页内容生成合适的动态演示，不固定为 3D。</p>
                            <el-input v-model="visualizationInstruction" type="textarea" :rows="5" :placeholder="currentVisualizationPlaceholder" />
                          </div>
                        </section>

                        <section
                          v-else-if="activeAssistantTab === 'workspace'"
                          key="workspace"
                          class="om-tool-panel om-workspace-panel"
                          :class="{ 'is-mindmap': activeTool === 'mindmap' }"
                        >
                          <header>
                            <strong>笔记与导图</strong>
                            <div class="om-mini-tabs">
                              <button type="button" :class="{ active: activeTool === 'note' }" @click="activeTool = 'note'">笔记</button>
                              <button type="button" :class="{ active: activeTool === 'mindmap' }" @click="activeTool = 'mindmap'">导图</button>
                            </div>
                          </header>
                          <template v-if="activeTool === 'mindmap'">
                            <VueFlow
                              v-model:nodes="mindmapNodes"
                              v-model:edges="mindmapEdges"
                              :fit-view-on-init="true"
                              class="classroom-mindmap-flow"
                            />
                          </template>
                          <template v-else>
                            <el-input v-model="noteMarkdown" type="textarea" :rows="13" placeholder="用 Markdown 写下当前页笔记" />
                            <div class="note-reference-card">
                              <span>引用页</span>
                              <strong>Slide {{ activeSlideIndex + 1 }} · {{ currentSlide?.title }}</strong>
                            </div>
                            <el-button type="primary" :loading="savingNote" :disabled="!noteMarkdown.trim()" @click="handleSaveNote">保存笔记</el-button>
                          </template>
                        </section>
                      </Transition>
                    </aside>
                  </div>
                </section>
              </section>
            </Transition>
          </section>

          <section v-else-if="activeGate === 'quiz'" key="quiz" class="classroom-pane">
            <Transition name="panel-swap" mode="out-in">
              <div v-if="classroom?.quiz_passed" key="quiz-done" class="gate-complete-panel">
                <strong>例题已通过</strong>
                <p v-if="latestQuizFeedback" class="task-feedback">{{ latestQuizFeedback }}</p>
                <div v-if="latestQuizResults.length" class="quiz-review-list">
                  <article v-for="result in latestQuizResults" :key="result.question_id" class="quiz-result-card" :class="{ correct: result.correct }">
                    <header>
                      <strong>{{ result.prompt }}</strong>
                      <el-tag :type="quizResultType(result)">{{ result.correct ? '正确' : '需复习' }}</el-tag>
                    </header>
                    <p>你的选择：{{ result.selected || '未作答' }}</p>
                    <p>正确答案：{{ result.expected }}</p>
                    <p>{{ result.explanation }}</p>
                  </article>
                </div>
                <div class="classroom-action-row is-sticky"><el-button type="primary" @click="activeGate = 'practice'">进入实操</el-button></div>
              </div>
              <div v-else key="quiz-form" class="classroom-form-stack">
                <el-alert v-if="!classroom?.slides_completed" title="请先翻完动态课件并完成课件学习" type="warning" :closable="false" />
                <div v-else class="quiz-list">
                  <article v-for="question in quizQuestions" :key="question.id" class="quiz-card">
                    <header>
                      <strong>{{ question.id }}. {{ question.prompt }}</strong>
                      <el-tag size="small" effect="plain">{{ question.question_type === 'multiple' ? '多选' : '单选' }}</el-tag>
                    </header>
                    <el-checkbox-group v-if="question.question_type === 'multiple'" :model-value="quizAnswerArray(question.id)" @update:model-value="setMultipleQuizAnswerValue(question.id, $event)">
                      <el-checkbox-button v-for="option in question.options" :key="option.label" :label="option.label">
                        {{ option.label }}. {{ option.text }}
                      </el-checkbox-button>
                    </el-checkbox-group>
                    <el-radio-group v-else :model-value="quizAnswerText(question.id)" @update:model-value="setSingleQuizAnswerValue(question.id, $event)">
                      <el-radio-button v-for="option in question.options" :key="option.label" :label="option.label">
                        {{ option.label }}. {{ option.text }}
                      </el-radio-button>
                    </el-radio-group>
                    <div v-if="quizResultMap[question.id]" class="quiz-result-inline" :class="{ correct: quizResultMap[question.id].correct }">
                      <strong>{{ quizResultMap[question.id].correct ? '回答正确' : '再想一想' }}</strong>
                      <p v-if="!quizResultMap[question.id].correct">提示：{{ quizResultMap[question.id].hint }}</p>
                      <p>{{ quizResultMap[question.id].explanation }}</p>
                    </div>
                  </article>
                </div>
                <p v-if="latestQuizFeedback" class="task-feedback">{{ latestQuizFeedback }}</p>
                <div v-if="quizMistakes.length" class="mistake-strip">
                  <strong>错题已加入错题本</strong>
                  <span v-for="mistake in quizMistakes" :key="mistake.question_id">{{ mistake.question_id }} · {{ mistake.knowledge_point }}</span>
                </div>
                <div class="classroom-action-row is-sticky">
                  <el-button v-if="latestQuizResults.length" @click="resetQuizAttempt">清空重答</el-button>
                  <el-button type="primary" :disabled="!classroom?.slides_completed" :loading="submittingQuiz" @click="handleSubmitQuiz">提交例题</el-button>
                </div>
              </div>
            </Transition>
          </section>

          <section v-else-if="activeGate === 'practice'" key="practice" class="classroom-pane">
            <Transition name="panel-swap" mode="out-in">
              <div v-if="classroom?.practice_passed" key="practice-done" class="gate-complete-panel">
                <strong>实操已通过</strong>
                <p v-if="latestPracticeFeedback" class="task-feedback">{{ latestPracticeFeedback }}</p>
                <div class="classroom-action-row"><el-button type="primary" @click="activeGate = 'reflection'">进入复盘</el-button></div>
              </div>
              <div v-else key="practice-form" class="classroom-form-stack">
                <h4>{{ practiceSpec?.title || '完成实操任务' }}</h4>
                <div v-if="practiceSpec" class="classroom-point-list">
                  <div v-for="step in practiceSteps" :key="step"><span>{{ step }}</span></div>
                </div>
                <el-input v-model="practiceForm.artifact_url" placeholder="产物链接或文件路径，可选" />
                <el-input v-model="practiceForm.key_result" type="textarea" :rows="3" placeholder="关键结果，例如指标、截图描述、运行结果" />
                <el-input v-model="practiceForm.report" type="textarea" :rows="7" placeholder="实操报告：说明你做了什么、如何验证、遇到什么问题、结果是否达标" />
                <p v-if="latestPracticeFeedback" class="task-feedback">{{ latestPracticeFeedback }}</p>
                <div class="classroom-action-row">
                  <el-button type="primary" :disabled="!pptPackage" :loading="submittingPractice" @click="handleSubmitPractice">提交实操</el-button>
                </div>
              </div>
            </Transition>
          </section>

          <section v-else key="reflection" class="classroom-pane">
            <Transition name="panel-swap" mode="out-in">
              <div v-if="classroom?.reflection_passed" key="reflection-done" class="gate-complete-panel">
                <strong>复盘已通过</strong>
                <p v-if="latestReflectionFeedback" class="task-feedback">{{ latestReflectionFeedback }}</p>
                <div class="classroom-action-row"><el-button @click="goBackToSyllabus">返回学习清单</el-button></div>
              </div>
              <div v-else key="reflection-form" class="classroom-form-stack">
                <h4>提交学习复盘</h4>
                <div v-if="reflectionPrompts.length" class="classroom-prompts">
                  <div v-for="prompt in reflectionPrompts" :key="prompt">{{ prompt }}</div>
                </div>
                <el-input v-model="reflectionForm.reflection" type="textarea" :rows="8" placeholder="写下本节学到的内容、完成证据、仍然薄弱的知识点" />
                <el-input v-model="unresolvedQuestionsText" type="textarea" :rows="3" placeholder="未解决问题，每行一个" />
                <el-input v-model="reflectionForm.next_action" placeholder="下一步行动" />
                <p v-if="latestReflectionFeedback" class="task-feedback">{{ latestReflectionFeedback }}</p>
                <div class="classroom-action-row">
                  <el-button type="primary" :disabled="!pptPackage" :loading="submittingReflection" @click="handleSubmitReflection">提交复盘</el-button>
                </div>
              </div>
            </Transition>
          </section>
        </Transition>
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { VueFlow, type Edge, type Node } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import {
  completeClassroomSlides,
  downloadClassroomResource,
  generateClassroomVisualization,
  generateClassroomPpt,
  getClassroomSession,
  getCurrentSyllabus,
  getOrCreateClassroomSession,
  saveClassroomNote,
  sendClassroomDialogue,
  submitClassroomPractice,
  submitClassroomQuiz,
  submitClassroomReflection,
  viewClassroomResource,
  type ClassroomVisualizationKind,
  type ClassroomResourceRead,
  type ClassroomSessionRead,
  type ClassroomSubmissionRead,
  type SyllabusVersionRead
} from '../services/apiClient'

type GateKey = 'ppt' | 'quiz' | 'practice' | 'reflection'
type ToolKey = 'lecture' | 'visualization' | 'note' | 'mindmap'
type AssistantTabKey = 'lecture' | 'interactive' | 'workspace'

const props = defineProps<{ projectId: number | null; itemId: number | null }>()
const router = useRouter()
const loading = ref(false)
const generatingVisualization = ref(false)
const loadingVisualizationView = ref(false)
const sendingDialogue = ref(false)
const savingNote = ref(false)
const submittingQuiz = ref(false)
const submittingPractice = ref(false)
const submittingReflection = ref(false)
const requestingPptGeneration = ref(false)
const pollingClassroom = ref(false)
let classroomPollTimer: ReturnType<typeof window.setInterval> | null = null
const syllabus = ref<SyllabusVersionRead | null>(null)
const classroom = ref<ClassroomSessionRead | null>(null)
const activeGate = ref<GateKey>('ppt')
const activeTool = ref<ToolKey>('lecture')
const activeAssistantTab = ref<AssistantTabKey | null>(null)
const activeSlideIndex = ref(0)
const visitedSlideIndices = ref<Set<number>>(new Set([0]))
const visualizationInstruction = ref('')
const visualizationKind = ref<ClassroomVisualizationKind>('auto')
const visualizationUrl = ref('')
const isSpeaking = ref(false)
const showLectureSubtitle = ref(false)
const noteMarkdown = ref('')
const chatMessage = ref('')
const unresolvedQuestionsText = ref('')
const quizAnswers = reactive<Record<string, string | string[]>>({})
const practiceForm = reactive({ report: '', artifact_url: '', key_result: '' })
const reflectionForm = reactive({ reflection: '', next_action: '' })
const quickActions = ['讲简单点', '举例', '出一道题', '联系科研方向', '总结本页']
const assistantTabs = [
  { key: 'lecture' as AssistantTabKey, label: '讲解' },
  { key: 'interactive' as AssistantTabKey, label: '互动' },
  { key: 'workspace' as AssistantTabKey, label: '产物' }
]

const visualizationKindOptions: Array<{ label: string; value: ClassroomVisualizationKind }> = [
  { label: '自动', value: 'auto' },
  { label: '图解', value: 'diagram' },
  { label: '模拟', value: 'simulation' },
  { label: '代码', value: 'code' },
  { label: '时间线', value: 'timeline' },
  { label: '3D', value: 'visualization3d' }
]

const currentItem = computed(() => syllabus.value?.items.find((item) => item.id === props.itemId) || null)
const pptResource = computed<ClassroomResourceRead | null>(() => {
  if (!classroom.value?.ppt_resource_id) return null
  return classroom.value.resources.find((resource) => resource.id === classroom.value?.ppt_resource_id) || null
})
const visualizationResource = computed<ClassroomResourceRead | null>(() => {
  const resources = classroom.value?.resources || []
  return [...resources].reverse().find((resource) => resource.resource_type === 'interactive_visualization') || null
})
const pptPackage = computed<Record<string, any> | null>(() => pptResource.value?.content_data || null)
const slideList = computed<any[]>(() => pptPackage.value?.slides || [])
const quizQuestions = computed<any[]>(() => pptPackage.value?.quiz || [])
const classroomGenerationState = computed(() => classroom.value?.progress_state || {})
const isClassroomGenerating = computed(() => classroom.value?.status === 'generating' || classroom.value?.status === 'queued' || pollingClassroom.value)
const classroomGenerationProgress = computed(() => {
  const value = Number(classroomGenerationState.value.generation_progress || 0)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, value))
})
const classroomGenerationTitle = computed(() => {
  if (classroom.value?.status === 'failed') return '课堂资源生成失败'
  if (classroom.value?.status === 'queued') return '课堂资源已排队'
  return '课堂资源正在生成'
})
const classroomGenerationMessage = computed(() => {
  if (classroom.value?.generation_error) return classroom.value.generation_error
  return String(classroomGenerationState.value.generation_message || '系统正在生成课件、例题、实操和复盘资源，完成后会自动显示。')
})
const currentSlide = computed(() => slideList.value[activeSlideIndex.value] || null)
const currentSlideLayout = computed(() => String(currentSlide.value?.layout || ''))
const currentSlideLayoutLabel = computed(() => {
  const labels: Record<string, string> = {
    cover: 'Overview',
    split_visual: 'Concept + Visual',
    process_timeline: 'Process',
    comparison_matrix: 'Comparison',
    evidence_cards: 'Evidence',
    lab_workbench: 'Lab',
    defense_panel: 'Defense'
  }
  return labels[currentSlideLayout.value] || currentSlideLayout.value
})
const currentSlideVisualBlocks = computed<Array<Record<string, string>>>(() => {
  const blocks = Array.isArray(currentSlide.value?.visual_blocks) ? currentSlide.value.visual_blocks : []
  return blocks.map((block: Record<string, unknown>) => ({
    type: String(block.type || 'concept'),
    title: String(block.title || ''),
    content: String(block.content || ''),
    emphasis: String(block.emphasis || '')
  })).filter((block: Record<string, string>) => block.title && block.content)
})
const currentSlideSidePanel = computed<{ title: string; items: string[] } | null>(() => {
  const panel = currentSlide.value?.side_panel
  if (!panel || typeof panel !== 'object') return null
  const items = Array.isArray(panel.items) ? panel.items.map((item: unknown) => String(item)).filter(Boolean) : []
  if (!String(panel.title || '').trim() || !items.length) return null
  return { title: String(panel.title), items }
})
const currentSlideTakeaways = computed<string[]>(() => {
  return Array.isArray(currentSlide.value?.takeaways) ? currentSlide.value.takeaways.map((item: unknown) => String(item)).filter(Boolean) : []
})
const currentSlideSourceRefs = computed<Array<{ title: string; url: string }>>(() => {
  if (!Array.isArray(currentSlide.value?.source_refs)) return []
  return currentSlide.value.source_refs
    .map((item: unknown) => {
      if (!item || typeof item !== 'object') return null
      const source = item as Record<string, unknown>
      const title = String(source.title || '').trim()
      const url = String(source.url || '').trim()
      if (!title || !/^https?:\/\//i.test(url)) return null
      return { title, url }
    })
    .filter((item: { title: string; url: string } | null): item is { title: string; url: string } => Boolean(item))
})
const currentSlideKnowledgePoints = computed<string[]>(() => {
  const title = String(currentSlide.value?.title || '')
  const bullets = (currentSlide.value?.bullets || []).join(' ')
  const matched = (currentItem.value?.knowledge_points || []).filter((point) => {
    const value = String(point)
    return title.includes(value) || bullets.includes(value)
  })
  return matched.length ? matched.slice(0, 4) : (currentItem.value?.knowledge_points || []).slice(0, 4)
})
const currentSlideExplanation = computed(() => {
  const notes = String(currentSlide.value?.speaker_notes || '').trim()
  if (notes) return notes
  const bullets = (currentSlide.value?.bullets || []).join('；')
  return bullets ? `本页围绕 ${currentSlide.value?.title || '当前知识点'} 展开：${bullets}` : '当前页暂无讲解内容。'
})
const slidesVisitedCount = computed(() => visitedSlideIndices.value.size)
const allSlidesViewed = computed(() => Boolean(slideList.value.length) && slidesVisitedCount.value >= slideList.value.length)
const conceptCards = computed<any[]>(() => pptPackage.value?.concept_cards || [])
const guidingQuestions = computed<any[]>(() => pptPackage.value?.guiding_questions || [])
const voiceScript = computed<Record<string, any>>(() => pptPackage.value?.voice_script || {})
const practiceSpec = computed(() => pptPackage.value?.practice || null)
const practiceSteps = computed<string[]>(() => practiceSpec.value?.steps || [])
const reflectionPrompts = computed<string[]>(() => pptPackage.value?.reflection_prompts || [])
const gates = computed(() => [
  { key: 'ppt' as GateKey, title: '课件学习', kind: '集成课堂', done: Boolean(classroom.value?.slides_completed) },
  { key: 'quiz' as GateKey, title: '回答例题', kind: '测验', done: Boolean(classroom.value?.quiz_passed) },
  { key: 'practice' as GateKey, title: '完成实操', kind: '实践', done: Boolean(classroom.value?.practice_passed) },
  { key: 'reflection' as GateKey, title: '提交复盘', kind: '复盘', done: Boolean(classroom.value?.reflection_passed) }
])
const activeGateMeta = computed(() => gates.value.find((gate) => gate.key === activeGate.value) || gates.value[0])
const completedGateCount = computed(() => gates.value.filter((gate) => gate.done).length)
const gateProgress = computed(() => Math.round((completedGateCount.value / 4) * 100))
const slideReadPercent = computed(() => {
  if (!slideList.value.length) return 0
  return Math.round((slidesVisitedCount.value / slideList.value.length) * 100)
})
const isDeckFocusMode = computed(() => activeGate.value === 'ppt' && Boolean(pptPackage.value))
const voiceText = computed(() => {
  if (!voiceScript.value && !currentSlide.value) return ''
  const title = currentSlide.value?.title ? `现在讲解：${currentSlide.value.title}。` : ''
  const notes = String(currentSlide.value?.speaker_notes || '').trim()
  const bullets = (currentSlide.value?.bullets || []).map((item: string, index: number) => `${index + 1}. ${item}`).join('。')
  const context = currentSlideKnowledgePoints.value.length ? `这一页的关键知识点包括：${currentSlideKnowledgePoints.value.join('、')}。` : ''
  const example = currentSlide.value?.example ? `举个例子：${currentSlide.value.example}` : ''
  const misconception = currentSlide.value?.misconception ? `常见误区是：${currentSlide.value.misconception}` : ''
  const interaction = currentSlide.value?.interaction_prompt ? `你可以思考：${currentSlide.value.interaction_prompt}` : ''
  const guidance = '请注意，这不是逐字朗读课件，而是用课堂讲解的方式说明概念、例子、易错点和下一步操作。'
  const body = notes || bullets || String(voiceScript.value.one_minute || voiceScript.value.five_minutes || '')
  return [title, context, body, example, misconception, interaction, guidance].filter(Boolean).join('\n')
})
const currentVisualizationPlaceholder = computed(() => {
  const title = currentSlide.value?.title || currentItem.value?.title || '当前页'
  const points = currentSlideKnowledgePoints.value.join('、') || '当前知识点'
  return `围绕「${title}」生成动态演示。可补充希望展示的机制，例如：${points} 的流程、信号传播、状态变化、数据流、交互动画或必要时的 3D 类比。`
})
const mindmapNodes = ref<Node[]>([])
const mindmapEdges = ref<Edge[]>([])
const latestSubmission = computed(() => {
  const submissions = classroom.value?.submissions || []
  return submissions[submissions.length - 1] || null
})
const latestFeedback = computed(() => latestSubmission.value?.feedback || '')
const latestQuizFeedback = computed(() => latestSubmissionByType('quiz')?.feedback || '')
const latestQuizSubmission = computed(() => latestSubmissionByType('quiz'))
const latestQuizResults = computed<Array<Record<string, any>>>(() => {
  const results = latestQuizSubmission.value?.content?.results
  return Array.isArray(results) ? results : []
})
const quizResultMap = computed<Record<string, Record<string, any>>>(() => Object.fromEntries(latestQuizResults.value.map((result) => [String(result.question_id), result])))
const quizMistakes = computed(() => latestQuizResults.value.filter((result) => !result.correct))
const latestPracticeFeedback = computed(() => latestSubmissionByType('practice')?.feedback || '')
const latestReflectionFeedback = computed(() => latestSubmissionByType('reflection')?.feedback || '')
const dialogueMessages = computed(() => {
  const submissions = classroom.value?.submissions || []
  return submissions
    .filter((submission) => submission.submission_type === 'dialogue_user' || submission.submission_type === 'dialogue_assistant')
    .map((submission) => ({
      role: String(submission.content.role || (submission.submission_type === 'dialogue_user' ? 'user' : 'assistant')),
      content: String(submission.content.message || ''),
      created_at: submission.created_at
    }))
})

onMounted(loadClassroom)
onBeforeUnmount(() => {
  revokeVisualizationUrl()
  stopVoice()
  stopClassroomPolling()
})
watch(() => [props.projectId, props.itemId] as const, () => loadClassroom())
watch(() => visualizationResource.value?.id, () => {
  if (visualizationResource.value) void loadVisualizationView()
  else revokeVisualizationUrl()
})

async function loadClassroom() {
  if (!props.projectId || !props.itemId) return
  loading.value = true
  try {
    const [{ data: syllabusData }, { data: classroomData }] = await Promise.all([
      getCurrentSyllabus(props.projectId),
      getOrCreateClassroomSession(props.itemId)
    ])
    syllabus.value = syllabusData
    classroom.value = classroomData
    hydrateQuizAnswers()
    syncVisitedSlidesFromSession()
    hydrateNote()
    hydrateMindmap()
    if (visualizationResource.value) await loadVisualizationView()
    if (!pptPackage.value) await ensurePptGeneration()
  } finally {
    loading.value = false
  }
}

async function ensurePptGeneration(forceRetry = false) {
  if (!classroom.value || classroom.value.ppt_resource_id || requestingPptGeneration.value) return
  if (classroom.value.status === 'failed' && !forceRetry) {
    ElMessage.error(classroom.value.generation_error || '课堂资源生成失败')
    return
  }
  requestingPptGeneration.value = true
  try {
    const { data } = await generateClassroomPpt(classroom.value.id)
    classroom.value = data
    startClassroomPolling()
  } finally {
    requestingPptGeneration.value = false
  }
}

function startClassroomPolling() {
  if (!classroom.value || classroomPollTimer) return
  pollingClassroom.value = true
  classroomPollTimer = window.setInterval(() => {
    void refreshClassroomStatus()
  }, 5000)
}

function stopClassroomPolling() {
  if (classroomPollTimer) {
    window.clearInterval(classroomPollTimer)
    classroomPollTimer = null
  }
  pollingClassroom.value = false
}

async function refreshClassroomStatus() {
  if (!classroom.value) return
  const { data } = await getClassroomSession(classroom.value.id)
  classroom.value = data
  if (data.ppt_resource_id) {
    stopClassroomPolling()
    hydrateQuizAnswers()
    syncVisitedSlidesFromSession()
    hydrateNote()
    hydrateMindmap()
    ElMessage.success('课堂课件已生成')
    return
  }
  if (data.status === 'failed') {
    stopClassroomPolling()
    ElMessage.error(data.generation_error || '课堂资源生成失败')
  }
}

async function handleGenerateVisualization() {
  if (!classroom.value) return
  generatingVisualization.value = true
  try {
    const pageContext = [
      `当前页：${currentSlide.value?.title || currentItem.value?.title || ''}`,
      `知识点：${currentSlideKnowledgePoints.value.join('、')}`,
      `页面要点：${(currentSlide.value?.bullets || []).join('；')}`,
      `用户要求：${visualizationInstruction.value}`
    ].join('\n')
    const { data } = await generateClassroomVisualization(classroom.value.id, {
      instruction: pageContext,
      preferred_kind: visualizationKind.value
    })
    classroom.value = data
    await loadVisualizationView()
    activeTool.value = 'visualization'
    activeAssistantTab.value = 'interactive'
    ElMessage.success('动态演示已生成')
  } finally {
    generatingVisualization.value = false
  }
}

function toggleAssistantTab(tab: AssistantTabKey) {
  if (activeAssistantTab.value === tab) {
    activeAssistantTab.value = null
    if (tab === 'lecture') stopVoice()
    return
  }
  activeAssistantTab.value = tab
  if (tab === 'lecture') activeTool.value = 'lecture'
  if (tab === 'interactive') {
    activeTool.value = 'visualization'
    stopVoice()
  }
  if (tab === 'workspace') {
    if (!['note', 'mindmap'].includes(activeTool.value)) activeTool.value = 'note'
    stopVoice()
  }
}

function toggleLectureVoice() {
  const text = voiceText.value.trim()
  if (!text) {
    ElMessage.warning('当前页暂无可讲解内容')
    return
  }
  if (isSpeaking.value) {
    window.speechSynthesis.pause()
    isSpeaking.value = false
    return
  }
  stopVoice()
  showLectureSubtitle.value = true
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 0.96
  utterance.pitch = 1
  utterance.onend = () => {
    isSpeaking.value = false
  }
  utterance.onerror = () => {
    isSpeaking.value = false
    ElMessage.error('浏览器语音播放失败，请检查系统语音服务')
  }
  isSpeaking.value = true
  window.speechSynthesis.speak(utterance)
}

function stopVoice() {
  window.speechSynthesis.cancel()
  isSpeaking.value = false
}

async function handleSaveNote() {
  if (!classroom.value || !noteMarkdown.value.trim()) return
  savingNote.value = true
  try {
    const { data } = await saveClassroomNote(classroom.value.id, {
      markdown: noteMarkdown.value,
      slide_index: activeSlideIndex.value,
      slide_title: String(currentSlide.value?.title || '')
    })
    classroom.value = data
    ElMessage.success('课堂笔记已保存')
  } finally {
    savingNote.value = false
  }
}

async function loadVisualizationView() {
  if (!visualizationResource.value) return
  loadingVisualizationView.value = true
  try {
    const { data } = await viewClassroomResource(visualizationResource.value.id)
    revokeVisualizationUrl()
    visualizationUrl.value = URL.createObjectURL(data)
  } finally {
    loadingVisualizationView.value = false
  }
}

async function handleSendDialogue() {
  if (!classroom.value || !chatMessage.value.trim()) return
  const message = chatMessage.value.trim()
  chatMessage.value = ''
  sendingDialogue.value = true
  try {
    const { data } = await sendClassroomDialogue(classroom.value.id, { message })
    classroom.value = data.session
  } finally {
    sendingDialogue.value = false
  }
}

function sendQuickAction(action: string) {
  if (!pptPackage.value) return
  chatMessage.value = action
  void handleSendDialogue()
}

function askGuidingQuestion(question: string) {
  chatMessage.value = question
  void handleSendDialogue()
}

function quizOptionLabel(question: Record<string, any>, value: string) {
  const options = Array.isArray(question.options) ? question.options : []
  const option = options.find((item: Record<string, any>) => String(item.label) === value)
  return option ? `${option.label}. ${option.text}` : value
}

function quizAnswerText(questionId: string) {
  const value = quizAnswers[questionId]
  return Array.isArray(value) ? value[0] || '' : String(value || '')
}

function quizAnswerArray(questionId: string) {
  const value = quizAnswers[questionId]
  if (Array.isArray(value)) return value
  return value ? [String(value)] : []
}

function setQuizAnswer(questionId: string, value: string | string[]) {
  quizAnswers[questionId] = value
}

function setMultipleQuizAnswerValue(questionId: string, value: unknown) {
  quizAnswers[questionId] = Array.isArray(value) ? value.map(String) : []
}

function setSingleQuizAnswerValue(questionId: string, value: unknown) {
  quizAnswers[questionId] = String(value || '')
}

function quizResultType(result: Record<string, any> | undefined) {
  if (!result) return 'info'
  return result.correct ? 'success' : 'warning'
}

function resetQuizAttempt() {
  for (const question of quizQuestions.value) {
    quizAnswers[question.id] = question.question_type === 'multiple' ? [] : ''
  }
}

async function handleSubmitQuiz() {
  if (!classroom.value) return
  submittingQuiz.value = true
  try {
    const answers = Object.fromEntries(Object.entries(quizAnswers).map(([key, value]) => [key, Array.isArray(value) ? value.join(',') : value]))
    const { data } = await submitClassroomQuiz(classroom.value.id, answers)
    classroom.value = data
    if (data.quiz_passed) activeGate.value = 'practice'
    ElMessage.success(data.quiz_passed ? '例题已通过' : '例题未通过，请修改后再提交')
  } finally {
    submittingQuiz.value = false
  }
}

function handleGateSelect(key: GateKey) {
  if (key !== 'ppt' && !classroom.value?.slides_completed) {
    activeGate.value = 'ppt'
    ElMessage.warning('请先完成课件学习')
    return
  }
  activeGate.value = key
}

function goToSlide(index: number) {
  if (!slideList.value.length) return
  activeSlideIndex.value = Math.min(Math.max(index, 0), slideList.value.length - 1)
  visitedSlideIndices.value = new Set([...visitedSlideIndices.value, activeSlideIndex.value])
}

async function handleCompleteSlides() {
  if (!classroom.value || !slideList.value.length) return
  const { data } = await completeClassroomSlides(classroom.value.id, {
    current_index: activeSlideIndex.value,
    total_slides: slideList.value.length,
    visited_indices: Array.from(visitedSlideIndices.value)
  })
  classroom.value = data
  activeGate.value = 'quiz'
  ElMessage.success('课件学习已完成，可以进入例题环节')
}

async function handleSubmitPractice() {
  if (!classroom.value) return
  submittingPractice.value = true
  try {
    const { data } = await submitClassroomPractice(classroom.value.id, { ...practiceForm })
    classroom.value = data
    if (data.practice_passed) activeGate.value = 'reflection'
    ElMessage.success(data.practice_passed ? '实操已通过' : '实操未通过，请根据反馈补充')
  } finally {
    submittingPractice.value = false
  }
}

async function handleSubmitReflection() {
  if (!classroom.value) return
  submittingReflection.value = true
  try {
    const { data } = await submitClassroomReflection(classroom.value.id, {
      reflection: reflectionForm.reflection,
      unresolved_questions: unresolvedQuestionsText.value.split('\n').map((line) => line.trim()).filter(Boolean),
      next_action: reflectionForm.next_action
    })
    classroom.value = data
    if (data.status === 'completed') {
      await refreshSyllabus()
      ElMessage.success('课堂已完成，学习进度已更新')
    } else {
      ElMessage.success(data.reflection_passed ? '复盘已通过' : '复盘未通过，请继续补充')
    }
  } finally {
    submittingReflection.value = false
  }
}

async function refreshSyllabus() {
  if (!props.projectId) return
  const { data } = await getCurrentSyllabus(props.projectId)
  syllabus.value = data
}

function hydrateQuizAnswers() {
  for (const question of quizQuestions.value) {
    if (quizAnswers[question.id] === undefined) quizAnswers[question.id] = question.question_type === 'multiple' ? [] : ''
  }
}

function syncVisitedSlidesFromSession() {
  const progress = classroom.value?.slide_progress || {}
  const rawVisited = Array.isArray(progress.visited_indices) ? progress.visited_indices : [0]
  const visited = rawVisited
    .map((index: unknown) => Number(index))
    .filter((index: number) => Number.isInteger(index) && index >= 0)
  visitedSlideIndices.value = new Set(visited.length ? visited : [0])
  const nextIndex = Number(progress.current_index)
  activeSlideIndex.value = Number.isInteger(nextIndex) && nextIndex >= 0 ? nextIndex : 0
  if (slideList.value.length) goToSlide(activeSlideIndex.value)
}

function latestSubmissionByType(type: string): ClassroomSubmissionRead | null {
  const submissions = classroom.value?.submissions.filter((submission) => submission.submission_type === type) || []
  return submissions[submissions.length - 1] || null
}

function downloadPpt() {
  if (!pptResource.value) return
  void downloadClassroomResource(pptResource.value.id).then(({ data }) => {
    downloadBlob(data, `${pptResource.value?.title || 'classroom'}.pptx`)
  })
}

function downloadVisualization() {
  if (!visualizationResource.value) return
  void downloadClassroomResource(visualizationResource.value.id).then(({ data }) => {
    downloadBlob(data, `${visualizationResource.value?.title || 'visualization'}.html`)
  })
}

function downloadBlob(data: Blob, filename: string) {
  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function visualBlockLabel(type: string) {
  const labels: Record<string, string> = {
    concept: 'Concept',
    process: 'Process',
    metric: 'Metric',
    evidence: 'Evidence',
    comparison: 'Compare',
    formula: 'Formula',
    code: 'Code',
    warning: 'Warning',
    question: 'Question'
  }
  return labels[type] || 'Insight'
}

function revokeVisualizationUrl() {
  if (visualizationUrl.value) URL.revokeObjectURL(visualizationUrl.value)
  visualizationUrl.value = ''
}

function hydrateNote() {
  const note = latestSubmissionByType('note')
  if (note?.content?.markdown) {
    noteMarkdown.value = String(note.content.markdown)
    return
  }
  noteMarkdown.value = [
    `# ${currentItem.value?.title || '课堂笔记'}`,
    '',
    `> 引用：Slide ${activeSlideIndex.value + 1} · ${currentSlide.value?.title || ''}`,
    '',
    '## 我的理解',
    '',
    '## 关键证据/公式/代码',
    '',
    '## 待追问'
  ].join('\n')
}

function hydrateMindmap() {
  const center = currentItem.value?.title || pptPackage.value?.title || '本课'
  const nodes: Node[] = [
    { id: 'center', type: 'default', label: center, position: { x: 360, y: 220 } }
  ]
  const edges: Edge[] = []
  const groups = [
    { id: 'points', label: '知识点', items: currentItem.value?.knowledge_points || [] },
    { id: 'concepts', label: '概念', items: conceptCards.value.map((card) => String(card.name || '')).filter(Boolean) },
    { id: 'practice', label: '实践', items: practiceSpec.value?.title ? [practiceSpec.value.title] : [] },
    { id: 'reflection', label: '复盘', items: reflectionPrompts.value.slice(0, 3) }
  ]
  groups.forEach((group, groupIndex) => {
    const groupNodeId = `group-${group.id}`
    nodes.push({
      id: groupNodeId,
      label: group.label,
      position: { x: 80 + groupIndex * 210, y: 60 }
    })
    edges.push({ id: `edge-center-${group.id}`, source: 'center', target: groupNodeId })
    group.items.slice(0, 5).forEach((item, itemIndex) => {
      const nodeId = `${group.id}-${itemIndex}`
      nodes.push({
        id: nodeId,
        label: String(item),
        position: { x: 40 + groupIndex * 210, y: 340 + itemIndex * 74 }
      })
      edges.push({ id: `edge-${group.id}-${itemIndex}`, source: groupNodeId, target: nodeId })
    })
  })
  mindmapNodes.value = nodes
  mindmapEdges.value = edges
}

async function goBackToSyllabus() {
  if (!props.projectId) return
  await router.push({ name: 'project-syllabus', params: { projectId: props.projectId } })
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '未开始',
    in_progress: '学习中',
    completed: '已完成',
    mastered: '已掌握',
    skipped: '已跳过'
  }
  return labels[status] || status
}

function statusType(status: string): '' | 'success' | 'warning' | 'info' | 'primary' {
  if (['completed', 'mastered'].includes(status)) return 'success'
  if (status === 'in_progress') return 'warning'
  if (status === 'skipped') return 'info'
  return 'primary'
}
</script>




