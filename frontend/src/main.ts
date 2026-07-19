import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'katex/dist/katex.min.css'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './styles.css'
import App from './AppRouted.vue'
import { router } from './router'
import { startGlobalMathRendering } from './services/mathRenderer'

createApp(App).use(router).use(ElementPlus).mount('#app')
startGlobalMathRendering(document.getElementById('app') || document.body)
