<template>
  <el-footer style="padding: 8px 16px; border-top: 1px solid var(--el-border-color-light); background: var(--el-bg-color);">
    <div style="display: flex; align-items: center; gap: 12px;">
      <el-progress
        :percentage="Math.round((store.progress.finished / Math.max(store.progress.total, 1)) * 100)"
        :stroke-width="16"
        :text-inside="false"
        :format="() => progressText"
        style="flex: 1;"
      />
      <span style="font-size: 13px; color: var(--el-text-color-secondary); white-space: nowrap;">
        {{ displayStep }}: {{ store.progress.message }}
      </span>
    </div>
  </el-footer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useForestStore } from '../stores/forest'

const store = useForestStore()

const progressLabel: Record<string, string> = {
  'aggregate': '聚合规则',
  'compute': '计算映射',
  'prepare': '准备中',
  'backup': '差异备份',
  'apply': '应用替换',
  'scan': '扫描 Steam 库',
  'restore': '恢复备份',
}

const displayStep = computed(() => {
  return progressLabel[store.progress.step] || store.progress.step
})

const progressText = computed(() => {
  const { finished, total } = store.progress
  return `${finished ?? 0}/${total ?? 1}`
})
</script>
