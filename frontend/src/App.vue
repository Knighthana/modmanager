<template>
  <LayoutShell />
  <div v-if="isMockMode" class="mock-watermark">[MOCK MODE]</div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import LayoutShell from './components/LayoutShell.vue'
import { apiPost } from './api/client'

const router = useRouter()

const isMockMode =
  import.meta.env.DEV && import.meta.env.VITE_ENABLE_MOCK === 'true'

onMounted(async () => {
  try {
    const resp = await apiPost('/workspace/status', {})
    if (resp.ok && resp.data) {
      const inputs = (resp.data as Record<string, any>).inputs || {}
      if (!inputs.user_config_path) {
        router.push('/settings')
      }
    }
  } catch {
    // Workspace not available yet — stay on default route
  }
})
</script>

<style scoped>
.mock-watermark {
  position: fixed;
  top: 4px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  background: rgba(255, 165, 0, 0.85);
  color: #fff;
  padding: 2px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
  pointer-events: none;
}
</style>
