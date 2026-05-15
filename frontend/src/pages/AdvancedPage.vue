<template>
  <div class="gui-page">
    <h2>高级 — 数据文件 JSON 查看</h2>

    <div style="margin-bottom: 16px;">
      <DatabaseSelector ref="databaseSelectorRef" />
    </div>

    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="Database" name="database">
          <div class="file-meta">
            <span class="meta-label">Database 名称:</span>
            <span class="meta-value">{{ databaseName || '—' }}</span>
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

        <el-tab-pane label="LocalStorage" name="localStorage">
          <div class="file-meta">
            <span class="meta-label">数据来源:</span>
            <span class="meta-value">window.localStorage (modmanager: 前缀)</span>
          </div>
          <el-input
            v-model="content.localStorage"
            type="textarea"
            :rows="20"
            readonly
            font-family="monospace"
          />
          <div class="action-bar">
            <el-button size="small" @click="refreshTab('localStorage')">刷新</el-button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { apiPost } from '../api/transport'
import DatabaseSelector from '../components/DatabaseSelector.vue'

const databaseSelectorRef = ref<InstanceType<typeof DatabaseSelector> | null>(null)
const databaseName = ref('')

const activeTab = ref('database')

const content = reactive<Record<string, string>>({
  database: '',
  aggregated: '',
  userConfig: '',
  localStorage: '',
})

const editing = reactive<Record<string, boolean>>({
  database: false,
  aggregated: false,
  userConfig: false,
  localStorage: false,
})

const tabStatus = reactive<Record<string, { type: 'success' | 'danger' | 'info'; msg: string } | null>>({
  database: null,
  aggregated: null,
  userConfig: null,
  localStorage: null,
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
        const dbName = databaseSelectorRef.value?.selectedDatabase ?? 'default'
        databaseName.value = dbName
        const resp = await apiPost<Record<string, unknown>>(
          '/database/read',
          { database_name: dbName },
        )
        if (resp.ok && resp.data) {
          raw = resp.data
        }
        break
      }
      case 'aggregated': {
        // 先从配置获取 aggregated_ruleset_output_path
        let path = 'aggregated_rule_set.json'
        try {
          const configResp = await apiPost<Record<string, unknown>>('/config/discover', {})
          if (configResp.ok && configResp.data) {
            const config = configResp.data as Record<string, unknown>
            if (config.aggregated_ruleset_output_path) {
              path = config.aggregated_ruleset_output_path as string
            }
          }
        } catch {
          // 使用默认路径
        }
        const resp = await apiPost<Record<string, unknown>>(
          '/rules/load-aggregated',
          { path },
        )
        if (resp.ok && resp.data) {
          raw = resp.data
        }
        break
      }
      case 'userConfig': {
        const resp = await apiPost<Record<string, unknown>>(
          '/config/discover',
          {},
        )
        if (resp.ok && resp.data) {
          raw = resp.data
        }
        break
      }
      case 'localStorage': {
        // Dump all modmanager-prefixed localStorage items
        const dump: Record<string, unknown> = {}
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i)
          if (key && key.startsWith('modmanager:')) {
            try {
              dump[key] = JSON.parse(localStorage.getItem(key) || '')
            } catch {
              dump[key] = localStorage.getItem(key)
            }
          }
        }
        raw = dump
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
        endpoint = '/database/save'
        payload = { database: parsed, database_name: databaseSelectorRef.value?.selectedDatabase ?? 'default' }
        break
      case 'aggregated':
        // Aggregated rules are auto-generated; saving not supported
        tabStatus.aggregated = { type: 'danger', msg: '聚合规则由系统自动生成，不支持手动保存' }
        return
      case 'userConfig':
        endpoint = '/config/save'
        payload = { config: parsed }
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

// Auto-refresh whichever tab becomes active.
watch(activeTab, (newVal) => {
  refreshTab(newVal)
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
