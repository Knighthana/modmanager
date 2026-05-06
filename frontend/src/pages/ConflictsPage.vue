<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <h2>冲突裁决</h2>
      <div style="display: flex; gap: 8px;">
        <el-button @click="onClearDecisions">重置决策</el-button>
        <el-button type="primary" @click="onRecalculate" :disabled="store.isRunning">
          重新计算
        </el-button>
      </div>
    </div>

    <!-- Empty state -->
    <el-empty v-if="store.conflictList.length === 0" description="暂无冲突，所有树已确定解析" />

    <!-- Conflict table -->
    <el-table
      v-else
      :data="store.conflictList"
      row-key="root_path"
      ref="tableRef"
      highlight-current-row
      @row-click="onRowClick"
    >
      <el-table-column prop="root_path" label="目标路径" min-width="200" />
      <el-table-column prop="destin_mixed_id" label="Destin" width="160" />
      <el-table-column label="候选操作" min-width="400">
        <template #default="{ row }">
          <el-radio-group
            :model-value="store.branchDecisions[row.root_path]"
            @change="(val: string) => store.setDecision(row.root_path, val)"
          >
            <el-radio
              v-for="c in row.candidates"
              :key="c"
              :value="c"
            >
              {{ formatCandidate(c) }}
            </el-radio>
          </el-radio-group>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useForestStore } from '../stores/forest'
import type { ConflictItem } from '../types'

const route = useRoute()
const store = useForestStore()
const tableRef = ref()

function formatCandidate(candidate: string): string {
  if (candidate === '!') return '删除此文件'
  if (candidate === '') return '保留此文件（跳过）'
  return `替换为 ${candidate}`
}

function onClearDecisions() {
  store.clearDecisions()
}

async function onRecalculate() {
  // Re-run pipeline with current decisions
  // Use the same params that were used before; for now we send a minimal payload
  // In a full implementation, params would be stored in the store or passed from ForestPage
  await store.runPipeline({
    database: {},
    kmm_rule_paths: [],
    user_config_path: '',
    backup_dir: '',
    dry_run: true,
    branch_decisions: { ...store.branchDecisions },
  })
}

function onRowClick(row: ConflictItem) {
  // Scroll to target row if clicked
  // This also supports the ?root_path=xxx URL param highlighting
}

onMounted(async () => {
  const rootPath = route.query.root_path as string | undefined
  if (rootPath && tableRef.value) {
    await nextTick()
    const row = store.conflictList.find(c => c.root_path === rootPath)
    if (row) {
      tableRef.value.setCurrentRow(row)
      // Scroll into view
      const el = document.querySelector(`[row-key="${rootPath}"]`)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }
})
</script>
