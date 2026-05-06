<template>
  <div>
    <h2>Forest 可视化</h2>

    <!-- 数据源发现面板 -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <span>数据源发现</span>
      </template>
      <el-form :model="store.pipelineForm" label-width="140px">
        <el-form-item label="Working pathstyle">
          <el-select v-model="store.pipelineForm.workingPathstyle" style="width: 200px;">
            <el-option label="auto" value="auto" />
            <el-option label="linux" value="linux" />
            <el-option label="windows" value="windows" />
          </el-select>
        </el-form-item>
        <el-form-item label="Greedy parsing">
          <el-switch v-model="store.pipelineForm.greedyParsing" />
        </el-form-item>
        <el-form-item label="Cache path">
          <el-input v-model="store.pipelineForm.cachePath" placeholder="/tmp/modmanager_database_generated.json" />
        </el-form-item>
        <el-form-item>
          <el-button
            type="warning"
            :loading="store.isRunning"
            :disabled="store.isRunning"
            @click="onDiscover"
          >
            {{ store.isRunning ? '探测中...' : '🔍 自动探测 Steam 库' }}
          </el-button>
        </el-form-item>
        <!-- 探测结果摘要 -->
        <el-form-item v-if="store.databaseSummary && !store.errors.length" label="探测结果">
          <el-tag type="success" style="margin-right: 8px;">
            发现 {{ store.databaseSummary.libraries }} 个库
          </el-tag>
          <el-tag type="success" style="margin-right: 8px;">
            {{ store.databaseSummary.games }} 个游戏
          </el-tag>
          <el-tag type="success">
            {{ store.databaseSummary.mods }} 个 mod
          </el-tag>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- PipelineForm -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <span>Pipeline 参数</span>
      </template>
      <el-form :model="store.pipelineForm" label-width="140px">
        <el-form-item label="Database 路径">
          <el-input v-model="store.pipelineForm.databasePath" placeholder="自动探测后自动填入">
            <template #append>
              <el-button @click="store.pipelineForm.databasePath = ''; store.pipelineForm.databaseJson = ''">清除</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="Database JSON (手动)">
          <el-input
            v-model="store.pipelineForm.databaseJson"
            type="textarea"
            :rows="3"
            placeholder='{"steamlib": [...], ...}'
            :disabled="!!store.pipelineForm.databasePath"
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
      <el-collapse>
        <el-collapse-item v-if="store.errors.length" title="错误 ({{ store.errors.length }})" name="errors">
          <el-alert
            v-for="(err, i) in store.errors"
            :key="'err-' + i"
            :title="err"
            type="error"
            :closable="false"
            style="margin-bottom: 4px;"
          />
        </el-collapse-item>
        <el-collapse-item v-if="store.warnings.length" title="警告 ({{ store.warnings.length }})" name="warnings">
          <el-alert
            v-for="(warn, i) in store.warnings"
            :key="'warn-' + i"
            :title="warn"
            type="warning"
            :closable="false"
            style="margin-bottom: 4px;"
          />
        </el-collapse-item>
      </el-collapse>
      <!-- 警告说明 -->
      <el-alert
        v-if="store.warnings.length > 0 && !store.errors.length"
        title="关于警告"
        type="info"
        :closable="false"
        style="margin-top: 8px;"
      >
        <template #default>
          <p>W_LOCAL_MOD_MISSING — 本地未安装该 mod，对应映射将被跳过</p>
          <p>W_NO_SOURCE_MATCH — mod 源文件不存在（可能未安装），对应条目将被跳过</p>
          <p>W_MISSING_SOURCE_ROOT / W_MISSING_DEST_ROOT — 缺少源/目标目录</p>
          <p>W_CREATE_TARGET_EXISTS_OVERWRITE — 目标文件已存在，将被覆盖；这是因为引擎对所有 action 统一检查，不会模拟 delete 执行后的状态，执行阶段 delete 会先执行，文件被删后 create 正常创建</p>
          <p>W_FOREST_BRANCHING — 该树有多个候选操作，需要用户裁决</p>
          <p>W_SOURCE_DELETED — 操作的源文件已被删除，该操作被跳过</p>
        </template>
      </el-alert>
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
import { computed, ref, watch } from 'vue'
import { useForestStore, generateBackupDir } from '../stores/forest'
import ForestViewer from '../components/ForestViewer.vue'
import type { TreeNode } from '../types'

const store = useForestStore()

const hasResult = computed(() => store.trees.length > 0 || store.errors.length > 0)

// 展示模式切换：仅显示分枝（pending）树
const showBranchingOnly = ref(false)

function getFilteredTrees(): TreeNode[] {
  if (!showBranchingOnly.value) return store.trees
  return store.trees.filter(t => t.resolved_state === 'pending')
}

const hasBranchingTrees = computed(() => store.trees.some(t => t.resolved_state === 'pending'))

async function onDiscover() {
  await store.discoverDatabase({
    mode: 'auto',
    paths: null,
    workingPathstyle: store.pipelineForm.workingPathstyle,
    greedyParsing: store.pipelineForm.greedyParsing,
    cachePath: store.pipelineForm.cachePath,
  })

  // Auto-populate form on success
  if (store.databaseSummary && !store.errors.length) {
    store.pipelineForm.databasePath = store.pipelineForm.cachePath
    store.pipelineForm.userConfigPath = '/tmp/modmanager_userconfig_generated.json'
    store.pipelineForm.backupDir = generateBackupDir()
  }
}

function prepareParams() {
  const rules = store.pipelineForm.rulesPaths
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)

  let database: Record<string, unknown>
  if (store.pipelineForm.databasePath && store.storedDatabase) {
    database = store.storedDatabase
  } else if (store.pipelineForm.databaseJson) {
    try {
      database = JSON.parse(store.pipelineForm.databaseJson)
    } catch {
      database = {}
    }
  } else {
    database = {}
  }

  return {
    database,
    kmm_rule_paths: rules,
    user_config_path: store.pipelineForm.userConfigPath || '',
    backup_dir: store.pipelineForm.backupDir || null,
  }
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
