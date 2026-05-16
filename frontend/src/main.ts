import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { migrateOldWorkspace } from './utils/persistence'
import './styles/gui-consistency.css'

// Element Plus 命令式调用组件的样式需显式导入
// (unplugin-vue-components 只自动加载 template 中使用的组件样式)
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-message.css'

async function bootstrap() {
  // One-time cleanup of old localStorage workspace key (before Pinia init)
  migrateOldWorkspace()

  if (import.meta.env.DEV && import.meta.env.VITE_ENABLE_MOCK === 'true') {
    const { worker } = await import('./mocks/browser')
    await worker.start({ onUnhandledRequest: 'bypass' })
    console.log('[MSW] Mock Service Worker started')
  }

  const app = createApp(App)
  app.use(router)
  app.use(createPinia())
  app.mount('#app')
}

bootstrap()
