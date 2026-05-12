<template>
  <div>
    <h2>高级 — 数据文件 JSON 查看</h2>

    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="Database" name="database">
          <div class="file-meta">
            <span class="meta-label">文件路径:</span>
            <span class="meta-value">{{ meta.database.path || '—' }}</span>
            <span v-if="meta.database.size" class="meta-sep">|</span>
            <span v-if="meta.database.size" class="meta-label">大小:</span>
            <span v-if="meta.database.size" class="meta-value">{{ meta.database.size }}</span>
            <span v-if="meta.database.mtime" class="meta-sep">|</span>
            <span v-if="meta.database.mtime" class="meta-label">最后修改:</span>
            <span v-if="meta.database.mtime" class="meta-value">{{ meta.database.mtime }}</span>
          </div>
          <el-input
            v-model="content.database"
            type="textarea"
            :rows="20"
            :readonly="!editing.database"
            font-family="monospace"
          />
          <div class="action-bar">
            <el-button size="small" @click="toggleEdit('database')">
              {{ editing.database ? '取消' : '编辑' }}
            </el-button>
            <el-button size="small" type="primary" :disabled="!editing.database" @click="saveTab('database')">
              保存
            </el-button>
            <el-button size="small" @click="refreshTab('database')">刷新</el-button>
            <el-tag v-if="tabStatus.database" :type="tabStatus.database.type" size="small" effect="plain">
              {{ tabStatus.database.msg }}
            </el-tag>
          </div>
        </el-tab-pane>

        <el-tab-pane label="Aggregated Rules" name="aggregated">
          <div class="file-meta">
            <span class="meta-label">文件路径:</span>
            <span class="meta-value">{{ meta.aggregated.path || '—' }}</span>
            <span v-if="meta.aggregated.size" class="meta-sep">|</span>
            <span v-if="meta.aggregated.size" class="meta-label">大小:</span>
            <span v-if="meta.aggregated.size" class="meta-value">{{ meta.aggregated.size }}</span>
            <span v-if="meta.aggregated.mtime" class="meta-sep">|</span>
            <span v-if="meta.aggregated.mtime" class="meta-label">最后修改:</span>
            <span v-if="meta.aggregated.mtime" class="meta-value">{{ meta.aggregated.mtime }}</span>
          </div>
          <el-input
            v-model="content.aggregated"
            type="textarea"
            :rows="20"
            :readonly="!editing.aggregated"
            font-family="monospace"
          />
          <div class="action-bar">
            <el-button size="small" @click="toggleEdit('aggregated')">
              {{ editing.aggregated ? '取消' : '编辑' }}
            </el-button>
            <el-button size="small" type="primary" :disabled="!editing.aggregated" @click="saveTab('aggregated')">
              保存
            </el-button>
            <el-button size="small" @click="refreshTab('aggregated')">刷新</el-button>
            <el-tag v-if="tabStatus.aggregated" :type="tabStatus.aggregated.type" size="small" effect="plain">
              {{ tabStatus.aggregated.msg }}
            </el-tag>
          </div>
        </el-tab-pane>

        <el-tab-pane label="User Config" name="userConfig">
          <div class="file-meta">
            <span class="meta-label">文件路径:</span>
            <span class="meta-value">{{ meta.userConfig.path || '—' }}</span>
            <span v-if="meta.userConfig.size" class="meta-sep">|</span>
            <span v-if="meta.userConfig.size" class="meta-label">大小:</span>
            <span v-if="meta.userConfig.size" class="meta-value">{{ meta.userConfig.size }}</span>
            <span v-if="meta.userConfig.mtime" class="meta-sep">|</span>
            <span v-if="meta.userConfig.mtime" class="meta-label">最后修改:</span>
            <span v-if="meta.userConfig.mtime" class="meta-value">{{ meta.userConfig.mtime }}</span>
          </div>
          <el-input
            v-model="content.userConfig"
            type="textarea"
            :rows="20"
            :readonly="!editing.userConfig"
            font-family="monospace"
          />
          <div class="action-bar">
            <el-button size="small" @click="toggleEdit('userConfig')">
              {{ editing.userConfig ? '取消' : '编辑' }}
            </el-button>
            <el-button size="small" type="primary" :disabled="!editing.userConfig" @click="saveTab('userConfig')">
              保存
            </el-button>
            <el-button size="small" @click="refreshTab('userConfig')">刷新</el-button>
            <el-tag v-if="tabStatus.userConfig" :type="tabStatus.userConfig.type" size="small" effect="plain">
              {{ tabStatus.userConfig.msg }}
            </el-tag>
          </div>
        </el-tab-pane>

        <el-tab-pane label="Workspace" name="workspace">
          <div class="file-meta">
            <span class="meta-label">数据来源:</span>
            <span class="meta-value">GET /api/workspace/status</span>
          </div>
          <el-input
            v-model="content.workspace"
            type="textarea"
            :rows="20"
            readonly
            font-family="monospace"
          />
          <div class="action-bar">
            <el-button size="small" @click="refreshTab('workspace')">刷新</el-button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { apiPost } from '../api/client'

const activeTab = ref('database')

interface MetaInfo {
  path: string
  size: string
  mtime: string
}

const meta = reactive<Record<string, MetaInfo>>({
  database: { path: '', size: '', mtime: '' },
  aggregated: { path: '', size: '', mtime: '' },
  userConfig: { path: '', size: '', mtime: '' },
  workspace: { path: '', size: '', mtime: '' },
})

const content = reactive<Record<string, string>>({
  database: '',
  aggregated: '',
  userConfig: '',
  workspace: '',
})

const editing = reactive<Record<string, boolean>>({
  database: false,
  aggregated: false,
  userConfig: false,
  workspace: false,
})

const tabStatus = reactive<Record<string, { type: 'success' | 'danger' | 'info'; msg: string } | null>>({
  database: null,
  aggregated: null,
  userConfig: null,
  workspace: null,
})

function toggleEdit(tab: string) {
  editing[tab as keyof typeof editing] = !editing[tab as keyof typeof editing]
  // Clear status when toggling edit
  tabStatus[tab as keyof typeof tabStatus] = null
}

function formatJson(obj: unknown): string {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

function tryParse(raw: string): unknown {
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

async function refreshTab(tab: string) {
  tabStatus[tab as keyof typeof tabStatus] = null

  try {
    let raw: unknown = null

    switch (tab) {
      case 'database': {
        const resp = await apiPost<{ database: Record<string, unknown>; path: string; size: number; mtime: string }>(
          '/api/database/load',
          {},
        )
        if (resp.ok && resp.data) {
          raw = resp.data.database
          meta.database.path = resp.data.path || ''
          meta.database.size = resp.data.size ? `${(resp.data.size / 1024).toFixed(1)} KB` : ''
          meta.database.mtime = resp.data.mtime || ''
        }
        break
      }
      case 'aggregated': {
        const resp = await apiPost<{ rules: Record<string, unknown>; path: string; size: number; mtime: string }>(
          '/api/rules/load-aggregated',
          {},
        )
        if (resp.ok && resp.data) {
          raw = resp.data.rules
          meta.aggregated.path = resp.data.path || ''
          meta.aggregated.size = resp.data.size ? `${(resp.data.size / 1024).toFixed(1)} KB` : ''
          meta.aggregated.mtime = resp.data.mtime || ''
        }
        break
      }
      case 'userConfig': {
        const resp = await apiPost<{ user_config: Record<string, unknown>; path: string; size: number; mtime: string }>(
          '/api/config/discover',
          {},
        )
        if (resp.ok && resp.data) {
          raw = resp.data.user_config
          meta.userConfig.path = resp.data.path || ''
          meta.userConfig.size = resp.data.size ? `${(resp.data.size / 1024).toFixed(1)} KB` : ''
          meta.userConfig.mtime = resp.data.mtime || ''
        }
        break
      }
      case 'workspace': {
        const fetchResp = await fetch('/api/workspace/status')
        const json = await fetchResp.json()
        if (json.ok && json.data) {
          raw = json.data
        }
        break
      }
    }

    if (raw !== null) {
      content[tab as keyof typeof content] = formatJson(raw)
      tabStatus[tab as keyof typeof tabStatus] = { type: 'info', msg: '已加载' }
    } else {
      tabStatus[tab as keyof typeof tabStatus] = { type: 'danger', msg: '加载失败或无数据' }
    }
  } catch {
    tabStatus[tab as keyof typeof tabStatus] = { type: 'danger', msg: '网络错误' }
  }
}

async function saveTab(tab: string) {
  const parsed = tryParse(content[tab as keyof typeof content])
  if (!parsed) {
    tabStatus[tab as keyof typeof tabStatus] = { type: 'danger', msg: 'JSON 格式无效' }
    return
  }

  try {
    let endpoint = ''
    let payload: Record<string, unknown> = {}

    switch (tab) {
      case 'database':
        endpoint = '/api/database/save'
        payload = { database: parsed, output_path: null }
        break
      case 'aggregated':
        // Aggregated rules are auto-generated; saving not supported
        tabStatus.aggregated = { type: 'danger', msg: '聚合规则由系统自动生成，不支持手动保存' }
        return
      case 'userConfig':
        endpoint = '/api/config/save'
        payload = { output_path: null, config: parsed }
        break
    }

    if (!endpoint) return

    const resp = await apiPost(endpoint, payload)
    if (resp.ok) {
      tabStatus[tab as keyof typeof tabStatus] = { type: 'success', msg: '已保存' }
      editing[tab as keyof typeof editing] = false
    } else {
      tabStatus[tab as keyof typeof tabStatus] = { type: 'danger', msg: resp.errors?.[0] || '保存失败' }
    }
  } catch {
    tabStatus[tab as keyof typeof tabStatus] = { type: 'danger', msg: '保存请求异常' }
  }
}

// Load first tab on mount
onMounted(() => {
  refreshTab('database')
})
</script>

<style scoped>
.file-meta {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
  padding: 6px 0;
  border-bottom: 1px solid #ebeef5;
}
.meta-label {
  color: #909399;
  margin-right: 4px;
}
.meta-value {
  color: #303133;
  font-family: 'Courier New', Courier, monospace;
  margin-right: 8px;
}
.meta-sep {
  color: #dcdfe6;
  margin-right: 8px;
}
.action-bar {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  align-items: center;
}
:deep(.el-textarea__inner) {
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.5;
}
</style>
