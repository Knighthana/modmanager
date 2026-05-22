<template>
  <div class="workspace-selector" style="display: flex; align-items: center; gap: 8px;">
    <el-select v-model="selectedWorkspaceId" placeholder="无可用工作区" style="width: 220px;">
      <el-option v-for="opt in options" :key="opt.value" :label="opt.label" :value="opt.value" />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { apiGet } from '../api/transport'

interface WorkspaceOption {
  label: string
  value: string
}

interface WorkspaceInfo {
  workspace_id: string
  name: string
}

interface WorkspaceListResponse {
  workspaces: WorkspaceInfo[]
}

const options = ref<WorkspaceOption[]>([])
const selectedWorkspaceId = ref('')

onMounted(async () => {
  try {
    const resp = await apiGet<WorkspaceListResponse>('/workspace/list')
    const workspaces = resp.data?.workspaces
    if (resp.ok && workspaces && workspaces.length > 0) {
      options.value = workspaces.map(w => ({ label: w.name, value: w.workspace_id }))
      selectedWorkspaceId.value = workspaces[0].workspace_id
    }
  } catch {
    // 接口不可用时 dropdown 显示占位符 "无可用工作区"
  }
})

defineExpose({ selectedWorkspaceId, options })
</script>
