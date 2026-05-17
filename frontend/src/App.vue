<template>
  <LayoutShell />
  <div v-if="isMockMode" class="mock-watermark">[MOCK MODE]</div>
</template>

<script setup lang="ts">
import LayoutShell from './components/LayoutShell.vue'

const isMockMode =
  import.meta.env.DEV && import.meta.env.VITE_ENABLE_MOCK === 'true'

// Phase 3: 旧 onMounted 中的 workspace status check 已移除（已迁移到 workspace 模型）
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
