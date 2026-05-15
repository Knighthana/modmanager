<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <h2>{{ STR.conflictsPage.title }}</h2>
      <div style="display: flex; gap: 8px;">
        <el-button @click="onClearDecisions">{{ STR.conflictsPage.resetDecisions }}</el-button>
        <el-button
          type="success"
          :disabled="Object.keys(store.branchDecisions).length === 0 || isSaving"
          :loading="isSaving"
          @click="onConfirmDecisions"
        >
          {{ STR.conflictsPage.confirmDecision }}
        </el-button>
        <el-tooltip
          v-if="!store.lastSuccessfulParams"
          :content="STR.conflictsPage.tooltipText"
          placement="top"
        >
          <el-button type="primary" @click="onRecalculate" :disabled="true">
            {{ STR.conflictsPage.recalculate }}
          </el-button>
        </el-tooltip>
        <el-button
          v-else
          type="primary"
          @click="onRecalculate"
          :disabled="store.isRunning"
        >
          {{ STR.conflictsPage.recalculate }}
        </el-button>
      </div>
    </div>

    <!-- Empty state -->
    <el-empty v-if="store.conflictList.length === 0" :description="STR.conflictsPage.noConflicts" />

    <!-- Conflict table -->
    <el-table
      v-else
      :data="store.conflictList"
      row-key="root_path"
      ref="tableRef"
      highlight-current-row
      @row-click="onRowClick"
    >
      <el-table-column prop="root_path" :label="STR.conflictsPage.targetPath" min-width="200" />
      <el-table-column prop="destin_mixed_id" :label="STR.conflictsPage.destin" width="160" />
      <el-table-column :label="STR.conflictsPage.candidates" min-width="400">
        <template #default="{ row }">
          <el-radio-group
            :model-value="store.branchDecisions[row.root_path]"
            @change="(val) => store.setDecision(row.root_path, val as string)"
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
import { savePersistent } from '../utils/persistence'
import type { ConflictItem } from '../types'
import { STR } from '../locales/zh-CN'
import { ElMessage } from 'element-plus'

const route = useRoute()
const store = useForestStore()
const tableRef = ref()
const isSaving = ref(false)

function formatCandidate(candidate: string): string {
  if (candidate === '!') return STR.conflictsPage.deleteFile
  if (candidate === '') return STR.conflictsPage.keepFile
  return STR.conflictsPage.replaceWith(candidate)
}

function onClearDecisions() {
  store.clearDecisions()
}

async function onConfirmDecisions() {
  isSaving.value = true
  try {
    savePersistent('conflicts.branchDecisions', { ...store.branchDecisions })
    ElMessage.success(STR.conflictsPage.saveDecisionSuccess)
  } catch {
    ElMessage.error(STR.conflictsPage.saveDecisionFailed)
  } finally {
    isSaving.value = false
  }
}

async function onRecalculate() {
  const lastParams = store.lastSuccessfulParams
  if (!lastParams) return

  await store.runPipeline({
    database_name: lastParams.database_name,
    aggregated_rule_set: lastParams.aggregated_rule_set,
    managed_entries: lastParams.managed_entries,
    branch_decisions: { ...store.branchDecisions },
    dry_run: lastParams.dry_run,
    action_orders: lastParams.action_orders,
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
