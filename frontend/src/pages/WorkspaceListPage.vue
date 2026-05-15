<template>
  <div style="padding: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <h2 style="margin: 0;">📂 工作区</h2>
      <el-button type="primary" @click="showCreateDialog = true">新建工作区</el-button>
    </div>

    <el-empty v-if="!loading && workspaces.length === 0" :description="'暂无工作区，点击\u201C新建工作区\u201D开始'" />

    <div v-else-if="loading" style="text-align: center; padding: 40px;">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
    </div>

    <div v-else style="display: flex; flex-direction: column; gap: 12px;">
      <el-card
        v-for="(ws, idx) in workspaces"
        :key="ws.workspace_id"
        shadow="hover"
      >
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <div style="font-weight: 700; font-size: 15px;">
              {{ ws.name }}
              <el-tag v-if="idx === 0" type="success" size="small" style="margin-left: 8px;">最新</el-tag>
            </div>
            <div style="font-size: 13px; color: var(--el-text-color-secondary); margin-top: 4px;">
              🗄 {{ ws.database_name }} &nbsp;|&nbsp;
              🕐 {{ formatDate(ws.updated_at) }}
            </div>
          </div>
          <div style="display: flex; gap: 8px;">
            <el-button size="small" type="primary" @click="enterWorkspace(ws)">
              进入
            </el-button>
            <el-button size="small" type="danger" plain @click="confirmDelete(ws)">
              删除
            </el-button>
          </div>
        </div>
      </el-card>
    </div>

    <!-- Create Dialog -->
    <el-dialog v-model="showCreateDialog" title="新建工作区" width="420px">
      <el-form label-position="top">
        <el-form-item label="工作区名称">
          <el-input v-model="newName" placeholder="例如：我的第一次实验" />
        </el-form-item>
        <el-form-item label="绑定 Database">
          <el-select v-model="newDatabase" placeholder="选择 database" style="width: 100%;">
            <el-option v-for="db in databases" :key="db" :label="db" :value="db" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!newName || !newDatabase" :loading="creating" @click="doCreate">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { apiPost } from '../api/transport'
import { API_ENDPOINTS } from '../api/config'
import { useAppStore } from '../stores/app'
import type { WorkspaceMeta } from '../types'

const router = useRouter()
const appStore = useAppStore()
const workspaces = ref<WorkspaceMeta[]>([])
const databases = ref<string[]>([])
const loading = ref(true)
const showCreateDialog = ref(false)
const creating = ref(false)
const newName = ref('')
const newDatabase = ref('')

async function loadWorkspaces() {
  loading.value = true
  try {
    const res = await apiPost<{ workspaces: WorkspaceMeta[] }>(API_ENDPOINTS.WORKSPACE_LIST, {})
    if (res.ok && res.data) {
      workspaces.value = res.data.workspaces || []
    }
  } catch (e) {
    ElMessage.error('获取工作区列表失败')
  } finally {
    loading.value = false
  }
}

async function loadDatabases() {
  try {
    const res = await apiPost<{ config: Record<string, unknown> }>('/api/config/discover', {})
    if (res.ok && res.data) {
      const cfg = res.data as Record<string, unknown>
      const dbs = cfg.databases as Record<string, { path: string }> | undefined
      databases.value = dbs ? Object.keys(dbs) : []
      if (databases.value.length > 0 && !newDatabase.value) {
        newDatabase.value = databases.value[0]
      }
    }
  } catch { /* ignore */ }
}

async function doCreate() {
  creating.value = true
  try {
    const res = await apiPost<{ workspace_id: string; meta: WorkspaceMeta }>(
      API_ENDPOINTS.WORKSPACE_CREATE,
      { name: newName.value, database_name: newDatabase.value }
    )
    if (res.ok && res.data) {
      showCreateDialog.value = false
      newName.value = ''
      await loadWorkspaces()
      enterWorkspace(res.data.meta)
    } else {
      ElMessage.error(res.errors?.[0] || '创建工作区失败')
    }
  } catch (e) {
    ElMessage.error('创建工作区失败')
  } finally {
    creating.value = false
  }
}

function enterWorkspace(ws: WorkspaceMeta) {
  appStore.setCurrentWorkspaceId(ws.workspace_id)
  router.push(`/workspace/${ws.workspace_id}/rules`)
}

async function confirmDelete(ws: WorkspaceMeta) {
  try {
    await ElMessageBox.confirm(`确定删除工作区"${ws.name}"？所有数据将被清除。`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    const res = await apiPost<{ deleted: string }>(
      `/api/workspace/${ws.workspace_id}/delete`,
      {}
    )
    if (res.ok) {
      appStore.clearUiStateFor(ws.workspace_id)
      ElMessage.success('工作区已删除')
      await loadWorkspaces()
    } else {
      ElMessage.error(res.errors?.[0] || '删除失败')
    }
  } catch { /* cancelled */ }
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

onMounted(() => {
  loadWorkspaces()
  loadDatabases()
})
</script>
