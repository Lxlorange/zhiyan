import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles.css'
import App from './AppRouted.vue'
import { router } from './router'

createApp(App).use(router).use(ElementPlus).mount('#app')
