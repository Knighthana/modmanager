<template>
  <div class="rules-overview-page gui-page">
    <h2>规则概览</h2>

    <!-- 规则来源 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <span class="section-title">规则来源</span>
      </template>
      <div v-if="loadingSources" class="loading-text">正在加载规则来源...</div>
      <template v-else>
        <div class="sources-list">
          <div v-for="src in ruleSources" :key="src" class="source-item">
            <el-icon><FolderOpened /></el-icon>
            <span class="source-path">{{ src }}</span>
          </div>
        </div>
        <div class="source-hint">
          <span class="hint-text">规则来源来自 user_config，可在设置页中管理。</span>
          <el-button size="small" text @click="$router.push('/settings')">前往设置页管理</el-button>
        </div>
      </template>
    </el-card>

    <!-- 发现的规则文件 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <span class="section-title">发现的规则文件</span>
      </template>

      <el-empty v-if="loadingFiles" description="正在扫描规则文件..." />
      <el-empty v-else-if="ruleFiles.length === 0" description="未发现规则文件，请先在设置页添加规则来源路径。" />

      <div v-else class="rule-file-list">
        <div
          v-for="file in ruleFiles"
          :key="file.path"
          class="rule-file-item"
        >
          <div class="rule-file-header">
            <el-checkbox v-model="file.checked" />
            <span class="file-name">{{ file.name }}</span>
            <el-button
              size="small"
              text
              @click="toggleExpand(file)"
            >
              {{ file.expanded ? '收起 ▲' : '展开 ▾' }}
            </el-button>
          </div>

          <!-- Expanded detail -->
          <div v-if="file.expanded" class="rule-file-detail">
            <div v-if="file.loading" class="detail-status">加载中...</div>
            <div v-else-if="file.error" class="detail-status detail-error">{{ file.error }}</div>
            <template v-else-if="file.detail">
              <!-- rule_meta_tag -->
              <div class="detail-section">
                <div class="detail-section-title">rule_meta_tag</div>
                <div class="detail-row">
                  <span class="meta-label">namespace:</span>
                  <span class="meta-value">{{ file.detail.rule_meta_tag.rulenamespace }}</span>
                  <el-divider direction="vertical" />
                  <span class="meta-label">name:</span>
                  <span class="meta-value">{{ file.detail.rule_meta_tag.rulename }}</span>
                </div>
                <div class="detail-row">
                  <span class="meta-label">author:</span>
                  <span class="meta-value">{{ formatAuthors(file.detail.rule_meta_tag.author) }}</span>
                </div>
                <div class="detail-row">
                  <span class="meta-label">description:</span>
                  <span class="meta-value">{{ file.detail.rule_meta_tag.description }}</span>
                </div>
              </div>

              <!-- Game coverage -->
              <div class="detail-section">
                <div class="detail-section-title">覆盖游戏</div>
                <div class="game-list">
                  <el-tag
                    v-for="g in file.detail.game"
                    :key="g.appid"
                    class="game-tag"
                    type="info"
                    effect="plain"
                  >
                    {{ getGameName(g.appid) }} ({{ g.appid }}) — {{ g.modid.length }} MOD
                  </el-tag>
                </div>
              </div>

              <!-- Mod details -->
              <div class="detail-section">
                <div class="detail-section-title">MOD 详情</div>
                <div v-if="file.detail.mod.length === 0" class="empty-mods">该规则文件未定义 MOD 条目</div>
                <div
                  v-for="m in file.detail.mod"
                  :key="m.mixed_id"
                  class="mod-item"
                >
                  <div class="mod-heading">
                    <span class="mod-nickname">{{ m.nickname || '(未命名)' }}</span>
                    <span class="mod-mixed-id">({{ m.mixed_id }})</span>
                  </div>
                  <div v-if="m.preview && m.preview.length" class="mod-files-row">
                    <span class="mod-files-label">preview:</span>
                    <span class="mod-files-value">{{ m.preview.join(', ') }}</span>
                  </div>
                  <div v-if="m.readme && m.readme.length" class="mod-files-row">
                    <span class="mod-files-label">readme:</span>
                    <span class="mod-files-value">{{ m.readme.join(', ') }}</span>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 保存规则选择 -->
    <div class="action-bar">
      <el-button
        type="primary"
        size="large"
        :loading="saving"
        :disabled="selectedCount === 0"
        @click="saveSelection"
      >
        保存规则选择
      </el-button>

      <transition name="el-fade-in">
        <div v-if="savedCount !== null" class="save-result">
          <el-alert
            :title="`已保存 ${savedCount} 条规则`"
            type="success"
            :closable="false"
            show-icon
          />
          <router-link to="/compute-prep" class="next-link">[进入计算准备]</router-link>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { FolderOpened } from '@element-plus/icons-vue'
import { apiPost } from '../api/client'
import { loadWorkspace, saveWorkspace, simpleHash } from '../utils/persistence'
import { useForestStore } from '../stores/forest'

// ── Types ──────────────────────────────────────────────────────────────

interface Author {
  nickname?: string
}

interface RuleMetaTag {
  rulenamespace: string
  rulename: string
  author: Author[]
  description: string
}

interface GameEntry {
  appid: string
  modid: string[]
}

interface ModEntry {
  mixed_id: string
  nickname?: string
  preview?: string[]
  readme?: string[]
}

interface KmmRuleDetail {
  schema_namespace: string
  schema_version: string
  rule_meta_tag: RuleMetaTag
  game: GameEntry[]
  mod: ModEntry[]
}

interface RuleFileItem {
  name: string
  path: string
  checked: boolean
  expanded: boolean
  loading: boolean
  error: string
  detail: KmmRuleDetail | null
}

// ── Game appid → name mapping ─────────────────────────────────────────

const GAME_NAMES: Record<string, string> = {
  '270150': 'RWR',
  '107410': 'Arma3',
  '730': 'CS:GO',
  '440': 'TF2',
}

function getGameName(appid: string): string {
  return GAME_NAMES[appid] ?? `Game[${appid}]`
}

// ── Reactive state ─────────────────────────────────────────────────────

const ruleSources = ref<string[]>([])
const ruleFiles = ref<RuleFileItem[]>([])
const loadingSources = ref(true)
const loadingFiles = ref(true)
const saving = ref(false)
const savedCount = ref<number | null>(null)

const selectedCount = computed(() => ruleFiles.value.filter((f) => f.checked).length)

// ── Lifecycle ──────────────────────────────────────────────────────────

onMounted(async () => {
  // Step 1: discover config to get rule_sources
  await loadRuleSources()
  // Step 2: scan rule files
  await scanRuleFiles()
})

async function loadRuleSources() {
  loadingSources.value = true
  try {
    const resp = await apiPost<Record<string, unknown>>(
      '/config/discover',
      {},
    )
    if (resp.ok && resp.data) {
      const uc = resp.data as Record<string, unknown>
      ruleSources.value = (uc.rule_sources as string[]) || []
    }
  } catch {
    // Silently handle — page shows empty sources with hint to go to settings
  } finally {
    loadingSources.value = false
  }
}

async function scanRuleFiles() {
  loadingFiles.value = true
  const allFiles: Array<{ name: string; path: string }> = []

  try {
    for (const source of ruleSources.value) {
      if (source.endsWith('/')) {
        // Directory — scan for .kmmrule.json files
        try {
          const resp = await apiPost<{ files: Array<{ name: string; path: string }> }>(
            '/rules/scan',
            { dir: source },
          )
          if (resp.ok && resp.data?.files) {
            allFiles.push(...resp.data.files)
          }
        } catch {
          // Skip directories that fail to scan
        }
      } else {
        // Individual file — add directly (any extension, e.g. .kmmrule.json, .json.example)
        const name = source.split('/').pop() || source
        allFiles.push({ name, path: source })
      }
    }
  } catch {
    // Silently handle
  }

  ruleFiles.value = allFiles.map((f) => ({
    name: f.name,
    path: f.path,
    checked: true,
    expanded: false,
    loading: false,
    error: '',
    detail: null,
  }))

  loadingFiles.value = false
}

// ── Expand / collapse ──────────────────────────────────────────────────

async function toggleExpand(file: RuleFileItem) {
  if (file.expanded) {
    file.expanded = false
    return
  }

  // If detail not loaded yet, fetch it
  if (!file.detail && !file.loading) {
    file.loading = true
    file.error = ''
    try {
      const resp = await apiPost<{ content: string; name: string; path: string; size: number }>('/rules/read', {
        path: file.path,
      })
      if (resp.ok && resp.data?.content) {
        file.detail = JSON.parse(resp.data.content) as KmmRuleDetail
      } else {
        file.error = resp.errors?.join('; ') ?? '读取规则文件失败'
      }
    } catch {
      file.error = '网络错误：无法读取规则文件'
    } finally {
      file.loading = false
    }
  }

  file.expanded = true
}

// ── Save selection ─────────────────────────────────────────────────────

async function saveSelection() {
  const forestStore = useForestStore()
  const selectedPaths = ruleFiles.value
    .filter((f) => f.checked)
    .map((f) => f.path)

  if (selectedPaths.length === 0) return

  saving.value = true
  savedCount.value = null

  try {
    // 1. Aggregate rules
    const aggResp = await apiPost<Record<string, unknown>>('/rules/aggregate', {
      paths: selectedPaths,
    })

    if (!aggResp.ok) {
      ElMessage.error(aggResp.errors?.join('; ') ?? '聚合规则失败')
      saving.value = false
      return
    }

    // Store aggregated rule set in memory for downstream pages.
    // Persist only metadata in workspace to keep local payload small.
    if (aggResp.data) {
      const payload = aggResp.data as Record<string, unknown>
      const {
        output_path,
        aggregated_hash,
        aggregated_at,
        rule_count: _ruleCount,
        ...ruleSet
      } = payload

      // Keep only rule-set shape in memory (without metadata fields)
      forestStore.aggregatedRuleSet = ruleSet

      const ws = loadWorkspace()
      ws.aggregatedRuleSet = null
      ws.aggregatedRuleMeta = {
        output_path: typeof output_path === 'string' ? output_path : '',
        aggregated_hash: typeof aggregated_hash === 'string' ? aggregated_hash : simpleHash(ruleSet),
        aggregated_at: typeof aggregated_at === 'string' ? aggregated_at : new Date().toISOString(),
        selected_rule_paths: selectedPaths,
      }
      ws.aggregatedRuleHash = ws.aggregatedRuleMeta.aggregated_hash
      // Also store selectedRulePaths per-database for database-specific access
      const dbName = ws.lastDatabase || 'default'
      if (!ws.perDatabase[dbName]) ws.perDatabase[dbName] = { decisions: {}, lastComputeSummary: null }
      ws.perDatabase[dbName].selectedRulePaths = selectedPaths
      saveWorkspace(ws)
    }

    // 3. Show success
    savedCount.value = selectedPaths.length
    ElMessage.success(`已保存 ${selectedPaths.length} 条规则`)
  } catch {
    ElMessage.error('保存规则选择时发生网络错误')
  } finally {
    saving.value = false
  }
}

// ── Helpers ────────────────────────────────────────────────────────────

function formatAuthors(authors: Author[]): string {
  if (!authors || authors.length === 0) return '—'
  return authors
    .map((a) => a.nickname ?? '佚名')
    .join(', ')
}
</script>

<style scoped>
.rules-overview-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 16px 24px;
}

.section-card {
  margin-bottom: 16px;
}

.section-title {
  font-weight: 600;
  font-size: 15px;
}

.loading-text {
  color: #909399;
  font-size: 13px;
}

/* ── Sources section ─────────────────────────────── */

.sources-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.source-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  color: #303133;
}

.source-path {
  word-break: break-all;
}

.source-hint {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}

.hint-text {
  color: #909399;
}

.settings-link {
  font-size: 13px;
}

/* ── Rule file list ─────────────────────────────── */

.rule-file-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rule-file-item {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 8px 12px;
  transition: box-shadow 0.2s;
}

.rule-file-item:hover {
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.rule-file-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  flex: 1;
  font-weight: 500;
  font-size: 14px;
  color: #303133;
  font-family: 'Courier New', Courier, monospace;
}

/* ── Detail section ─────────────────────────────── */

.rule-file-detail {
  margin-top: 10px;
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 4px;
  border: 1px solid #ebeef5;
}

.detail-status {
  color: #909399;
  font-size: 13px;
  padding: 8px 0;
}

.detail-error {
  color: #f56c6c;
}

.detail-section {
  margin-bottom: 12px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-section-title {
  font-weight: 600;
  font-size: 13px;
  color: #606266;
  margin-bottom: 4px;
  padding-bottom: 2px;
  border-bottom: 1px dashed #e4e7ed;
}

.detail-row {
  font-size: 13px;
  line-height: 1.8;
  color: #303133;
}

.meta-label {
  color: #909399;
  margin-right: 4px;
}

.meta-value {
  color: #303133;
}

/* ── Game tags ──────────────────────────────────── */

.game-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.game-tag {
  font-size: 12px;
}

/* ── Mod items ──────────────────────────────────── */

.empty-mods {
  color: #c0c4cc;
  font-size: 12px;
  font-style: italic;
}

.mod-item {
  padding: 6px 8px;
  margin-bottom: 4px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #f0f2f5;
}

.mod-item:last-child {
  margin-bottom: 0;
}

.mod-heading {
  font-size: 13px;
  margin-bottom: 2px;
}

.mod-nickname {
  font-weight: 600;
  color: #303133;
}

.mod-mixed-id {
  color: #909399;
  font-size: 12px;
  font-family: 'Courier New', Courier, monospace;
}

.mod-files-row {
  font-size: 12px;
  color: #606266;
  line-height: 1.6;
  padding-left: 8px;
}

.mod-files-label {
  color: #909399;
  margin-right: 4px;
}

.mod-files-value {
  font-family: 'Courier New', Courier, monospace;
  color: #409eff;
}

/* ── Action bar ─────────────────────────────────── */

.action-bar {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

.save-result {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.next-link {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
}
</style>
