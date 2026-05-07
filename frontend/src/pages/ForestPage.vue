<template>
  <div>
    <h2>Forest 可视化</h2>

    <!-- PipelineForm -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <span>Pipeline 参数</span>
      </template>
      <el-form :model="store.pipelineForm" label-width="140px">
        <el-form-item label="Database 路径">
          <div style="display: flex; align-items: center; gap: 8px; width: 100%;">
            <el-input
              v-model="dbPathDisplay"
              :placeholder="store.dbManualOverride ? '输入 database.json 路径' : ''"
              :disabled="!store.dbManualOverride"
              style="flex: 1;"
              :ref="(el: any) => dbInputRef = el"
              @blur="onDbPathBlur"
            >
              <template v-if="!store.dbManualOverride" #suffix>
                <span>🔒</span>
              </template>
            </el-input>

            <!-- ℹ️ 信息气泡 -->
            <span
              style="cursor: pointer; font-size: 16px; color: var(--el-color-info); flex-shrink: 0;"
              @click="showDbInfo"
            >ℹ️</span>

            <!-- 手动填写/使用自动按钮 -->
            <el-button
              type="primary"
              size="default"
              style="flex-shrink: 0;"
              @click="onDbManualOverride"
            >
              {{ store.dbManualOverride ? '使用自动' : '手动填写' }}
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="Database JSON">
          <el-input
            v-model="store.pipelineForm.databaseJson"
            type="textarea"
            :rows="7"
            placeholder='{
  &quot;comment&quot;: {
    &quot;string1&quot;: &quot;留空使用上方路径中的文件，否则将会使用本栏中的任何输入作为database的输入来源&quot;
  },
  &quot;steamlib&quot;: [...],
  ...
}'
          />
        </el-form-item>
        <el-form-item label="Rules paths">
          <el-input v-model="store.pipelineForm.rulesPaths" placeholder="Comma-separated paths to kmm_rule files" />
        </el-form-item>
        <el-form-item label="User config 路径">
          <el-input v-model="store.pipelineForm.userConfigPath" placeholder="自动探测后自动填入" />
        </el-form-item>
        <el-form-item label="Backup dir">
          <el-input v-model="store.pipelineForm.backupDir" placeholder="自动推导（留空则自动）" />
        </el-form-item>
        <el-form-item label="Dry run">
          <el-switch v-model="store.pipelineForm.dryRun" />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="store.isRunning"
            :disabled="store.isRunning"
            @click="onCompute"
          >
            {{ store.isRunning ? '计算中...' : '📊 计算映射' }}
          </el-button>
          <el-button
            type="success"
            :loading="store.isRunning"
            :disabled="store.isRunning"
            @click="onRun"
            style="margin-left: 8px;"
          >
            ⚡ 应用流水线
          </el-button>
          <span style="margin-left: 8px; font-size: 12px; color: #999;">
            "计算映射"仅分析不修改文件 | "应用流水线"将执行备份+替换
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- ResultSummary -->
    <el-row v-if="hasResult" :gutter="16" style="margin-bottom: 16px;">
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">Trees 结点</span>
          <div style="font-size: 24px; font-weight: 600;">{{ store.trees.length }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">冲突</span>
          <div style="font-size: 24px; font-weight: 600;">{{ store.conflictList.length }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">最终映射</span>
          <div style="font-size: 24px; font-weight: 600;">{{ store.finalMapping.length }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">错误</span>
          <div style="font-size: 24px; font-weight: 600; color: var(--el-color-danger);">{{ store.errors.length }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 错误与警告面板 -->
    <div v-if="store.errors.length || store.warnings.length" style="margin-bottom: 16px;">
      <el-collapse v-model="activeCollapseNames">
        <el-collapse-item v-if="store.errors.length" title="错误 ({{ store.errors.length }})" name="errors">
          <el-alert
            v-for="(err, i) in store.errors"
            :key="'err-' + i"
            :title="err"
            type="error"
            :closable="false"
            style="margin-bottom: 4px; cursor: pointer;"
            @click="(e: MouseEvent) => onMessageClick(err, e)"
          />
        </el-collapse-item>
        <el-collapse-item v-if="store.warnings.length" title="警告 ({{ store.warnings.length }})" name="warnings">
          <el-alert
            v-for="(warn, i) in store.warnings"
            :key="'warn-' + i"
            :title="warn"
            type="warning"
            :closable="false"
            style="margin-bottom: 4px; cursor: pointer;"
            @click="(e: MouseEvent) => onMessageClick(warn, e)"
          />
        </el-collapse-item>
      </el-collapse>

      <!-- 提示：若全是 W_LOCAL_MOD_MISSING，建议先运行自动探测 -->
      <el-alert
        v-if="store.errors.every(e => e.startsWith('W_')) && store.errors.length > 0"
        title="提示"
        description="所有错误均为 warning 级别（如 W_LOCAL_MOD_MISSING），通常是因为数据源为空。请先切换到上方'数据源发现'面板，运行'自动探测 Steam 库'获取数据库后再试。"
        type="info"
        :closable="false"
        style="margin-top: 8px;"
      />
    </div>

    <!-- 展示模式切换 -->
    <el-card v-if="hasResult" shadow="never" style="margin-bottom: 16px;">
      <el-form label-width="140px">
        <el-form-item label="展示模式">
          <el-switch
            v-model="showBranchingOnly"
            active-text="仅分枝"
            inactive-text="全部树"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 无分枝冲突提示 -->
    <el-alert
      v-if="showBranchingOnly && store.trees.length > 0 && !hasBranchingTrees"
      title="无分枝冲突"
      type="info"
      :closable="false"
      description="当前所有树均已裁决，没有待处理的分枝冲突。"
      style="margin-bottom: 16px;"
    />

    <!-- ForestViewer -->
    <ForestViewer />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useForestStore, generateBackupDir } from '../stores/forest'
import ForestViewer from '../components/ForestViewer.vue'
import { apiPost } from '../api/client'
import type { TreeNode } from '../types'
import { showPopup } from '../utils/notify'
import { getDescription } from '../utils/errorCodes'

const store = useForestStore()

const hasResult = computed(() => store.trees.length > 0 || store.errors.length > 0)

const activeCollapseNames = computed(() => {
  const names: string[] = []
  if (store.errors.length) names.push('errors')
  if (store.warnings.length) names.push('warnings')
  return names
})

// Database path display: when locked (dbManualOverride=false), show augmented text;
// when unlocked (dbManualOverride=true), show pure path and allow write.
const dbPathDisplay = computed({
    get(): string {
        // 锁定状态：显示带后缀的完整文字
        if (!store.dbManualOverride) {
            const base = store.storedDatabase 
                ? 'Frontend Storage' 
                : (store.pipelineForm.databasePath || '');
            if (!base) return '';
            return `${base} (从数据源页面自动传入)`;
        }
        // 解锁状态：仅显示路径
        return store.pipelineForm.databasePath || '';
    },
    set(value: string) {
        store.pipelineForm.databasePath = value;
    }
})

// 展示模式切换：仅显示分枝（pending）树
const showBranchingOnly = ref(false)

// Database path manual override
const dbInputRef = ref<any>(null)

function onDbManualOverride() {
  if (!store.dbManualOverride) {
    // 解锁：启用输入 + 自动全选文字
    store.dbManualOverride = true;
    nextTick(() => {
      const input = dbInputRef.value;
      if (input) {
        // el-input 的 ref 获取内部 input 元素
        const nativeInput = input.$el?.querySelector('input') || input.$el;
        if (nativeInput) {
          nativeInput.select();
        }
      }
    });
  } else {
    // 重新锁定：input 内容自动恢复为 dbPathDisplay computed
    store.dbManualOverride = false;
  }
}

async function onDbPathBlur() {
    if (!store.dbManualOverride) return;
    const path = store.pipelineForm.databasePath;
    if (!path) return;

    try {
        const resp = await apiPost('/database/load', { path });
        if (resp.ok && resp.data) {
            store.storedDatabase = resp.data as Record<string, unknown>;
        }
    } catch {
        // 静默失败，用户可继续手动调整
    }
}

function getFilteredTrees(): TreeNode[] {
  if (!showBranchingOnly.value) return store.trees
  return store.trees.filter(t => t.resolved_state === 'pending')
}

const hasBranchingTrees = computed(() => store.trees.some(t => t.resolved_state === 'pending'))

const isDiscoverDisabled = computed(() =>
  store.pipelineForm.discoveryMode === 'manual' && !store.pipelineForm.manualSteamPath
)

async function onDiscover() {
  await store.discoverDatabase()

  // Auto-populate form on success
  if (store.databaseSummary && !store.errors.length) {
    store.pipelineForm.databasePath = store.pipelineForm.cachePath
    store.pipelineForm.backupDir = generateBackupDir()

    // Also discover + save user_config as a separate step
    await store.loadConfig()
    if (store.userConfig) {
      store.pipelineForm.userConfigPath = '/tmp/modmanager_userconfig_generated.json'
    }
  }
}

function prepareParams() {
  const rules = store.pipelineForm.rulesPaths
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)

  let database: any

  // 优先级 1: Database JSON 非空 → 以此为输入
  if (store.pipelineForm.databaseJson.trim()) {
    try {
      database = JSON.parse(store.pipelineForm.databaseJson)
    } catch {
      database = {}
    }
  }
  // 优先级 2: 自动模式 — storedDatabase 存在（来自自动传入或手动加载）
  else if (!store.dbManualOverride && store.storedDatabase) {
    database = store.storedDatabase
  }
  // 优先级 3: 手动模式 — 发路径字符串，后端自行 resolve + load
  else if (store.dbManualOverride && store.pipelineForm.databasePath) {
    database = store.pipelineForm.databasePath
  }
  // 优先级 4: 无可用数据
  else {
    database = {}
  }

  return {
    database,
    kmm_rule_paths: rules,
    user_config_path: store.pipelineForm.userConfigPath || '',
    backup_dir: store.pipelineForm.backupDir || null,
  }
}

function onMessageClick(msg: string, e: MouseEvent) {
    const desc = getDescription(msg)
    if (desc) {
        showPopup(desc, e.currentTarget as HTMLElement, e)
    }
}

function showDbInfo(e: MouseEvent) {
    showPopup(
        '数据源已在 📡 数据源 页面中配置。<br/>若已从数据源页应用，数据库将自动传入；否则可在此手动填写。',
        e.currentTarget as HTMLElement,
        e
    )
}

async function fetchVisualizationWithFilter() {
  const filtered = getFilteredTrees()
  if (filtered.length === 0) {
    store.svgContent = ''
    return
  }
  await store.fetchVisualization(filtered)
}

async function onCompute() {
  const params = prepareParams()
  await store.computeOnly({
    ...params,
    dry_run: true,
  })

  // 计算完成后，获取可视化
  if (store.trees.length > 0) {
    await fetchVisualizationWithFilter()
  }
}

async function onRun() {
  const params = prepareParams()
  await store.runPipeline({
    ...params,
    dry_run: store.pipelineForm.dryRun,
  })

  // 运行完成后，获取可视化
  if (store.trees.length > 0) {
    await fetchVisualizationWithFilter()
  }
}

// 切换展示模式时自动重新请求可视化
watch(showBranchingOnly, () => {
  if (store.trees.length > 0) {
    fetchVisualizationWithFilter()
  }
})
</script>
