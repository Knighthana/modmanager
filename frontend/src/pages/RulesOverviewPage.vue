<template>
  <div class="rules-overview-page gui-page">
    <h2>📋 规则概览</h2>

    <!-- 规则来源 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <span class="section-title">规则来源</span>
      </template>
      <div v-if="loadingSources" class="loading-text">正在加载规则来源...</div>
      <template v-else>
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
          <span style="font-size: 13px; color: #606266; white-space: nowrap;">选择来源：</span>
          <el-select v-model="selectedSource" placeholder="请选择规则来源" style="width: 300px;">
            <el-option
              v-for="name in sourceNames"
              :key="name"
              :label="name"
              :value="name"
            />
          </el-select>
        </div>
        <div class="source-hint">
          <span class="hint-text">规则来源来自 user_config，可在设置页中管理。</span>
          <el-button size="small" text class="subtle-link" @click="$router.push('/settings')">前往设置面板管理</el-button>
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
            <div class="file-name-row">
              <span class="file-display-name">{{ getDisplayName(file) }}</span>
              <span class="file-path-name">{{ file.name }}</span>
            </div>
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
                <div class="detail-section-title">规则文件元信息</div>
                <div class="detail-row">
                  <span class="meta-label">namespace:</span>
                  <span class="meta-value">{{ getRuleMetaDisplay(file.detail.rule_meta_tag.rulenamespace, 'anonymousnamespace') }}</span>
                  <el-divider direction="vertical" />
                  <span class="meta-label">rulename:</span>
                  <span class="meta-value">{{ getRuleMetaDisplay(file.detail.rule_meta_tag.rulename, 'unknownrulename') }}</span>
                </div>
                <div class="detail-row">
                  <span class="meta-label">author:</span>
                  <span v-if="!file.detail.rule_meta_tag.author || file.detail.rule_meta_tag.author.length === 0">—</span>
                  <template v-for="(a, ai) in file.detail.rule_meta_tag.author" :key="ai">
                    <el-popover placement="top" :width="240" trigger="click">
                      <template #reference>
                        <el-button size="small" text type="primary">{{ a.nickname ?? '佚名' }}</el-button>
                      </template>
                      <div style="font-size:13px;line-height:1.6;">
                        <div v-for="(v, k) in a" :key="k" style="display:flex;gap:8px;">
                          <span style="color:#999;min-width:60px;">{{ k }}</span>
                          <span>{{ typeof v === 'string' ? v : JSON.stringify(v) }}</span>
                        </div>
                      </div>
                    </el-popover>
                  </template>
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
        :loading="saving"
        :disabled="selectedCount === 0"
        @click="saveSelection"
      >
        💾 保存规则选择
      </el-button>
      <el-button
        type="success"
        :disabled="savedCount === null"
        @click="$router.push(`/workspace/${$route.params.workspaceId}/compute`)"
      >
        ✅ 进入计算准备
      </el-button>

      <transition name="el-fade-in">
        <div v-if="savedCount !== null" class="save-result">
          <el-alert
            :title="`已保存 ${savedCount} 条规则`"
            type="success"
            :closable="false"
            show-icon
          />
        </div>
      </transition>
    </div>


  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiPost, apiGet } from '../api/transport'
import { useAppStore } from '../stores/app'
import { useForestStore } from '../stores/forest'
import { getDescription } from '../utils/errorCodes'

const route = useRoute()
const appStore = useAppStore()

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

// ── Game appid → name mapping (loaded from database) ──────────────────

const gameNames = ref<Record<string, string>>({})

async function loadGameNames() {
  try {
    const resp = await apiPost<{ game?: Array<{ appid: string; name: string }> }>('/database/read', { database_name: 'default' })
    if (resp.ok && resp.data?.game) {
      const map: Record<string, string> = {}
      for (const g of resp.data.game) {
        if (g.appid && g.name) map[g.appid] = g.name
      }
      gameNames.value = map
    }
  } catch { /* silent */ }
}

function getGameName(appid: string): string {
  return gameNames.value[appid] ?? `Game[${appid}]`
}

function getRuleMetaDisplay(val: string | undefined, fallback: string): string {
  if (val === undefined || val === '') return fallback
  return val
}

function getDisplayName(file: RuleFileItem): string {
  if (file.detail) {
    const games = file.detail.game || []
    const mods = file.detail.mod || []
    const gameName = games.length > 0 ? getGameName(games[0].appid) : ''
    const modName = mods.length > 0 ? (mods[0].nickname || mods[0].mixed_id?.split(':')[1] || '') : ''
    if (gameName && modName) return `${gameName}-${modName}`
    if (gameName) return gameName
    return file.detail.rule_meta_tag?.rulename || 'unknownrulename'
  }
  return file.name
}

function showAuthorDetail(authors: Author[]) {
  if (!authors || authors.length === 0) return
  const lines = authors.map(a => a.nickname ?? '佚名')
  ElMessage.info(lines.join('、'))
}

// ── Reactive state ─────────────────────────────────────────────────────

const sourceNames = ref<string[]>([])
const selectedSource = ref('')
const ruleFiles = ref<RuleFileItem[]>([])
const loadingSources = ref(true)
const loadingFiles = ref(false)
const saving = ref(false)
const savedCount = ref<number | null>(null)

const selectedCount = computed(() => ruleFiles.value.filter((f) => f.checked).length)

// ── Lifecycle ──────────────────────────────────────────────────────────

onMounted(async () => {
  const workspaceId = route.params.workspaceId as string
  if (workspaceId) {
    appStore.setCurrentWorkspaceId(workspaceId)
  }
  await loadSourceNames()
  loadGameNames()
  await autoRestoreAggregated()
})

async function loadSourceNames() {
  loadingSources.value = true
  try {
    const resp = await apiPost<{ source_names: string[] }>('/rules/list-sources', {})
    if (resp.ok && resp.data) {
      sourceNames.value = resp.data.source_names || []
      if (sourceNames.value.length > 0 && !selectedSource.value) {
        selectedSource.value = sourceNames.value[0]
      }
    }
  } catch {
    // Silently handle — page shows empty sources with hint to go to settings
  } finally {
    loadingSources.value = false
  }
}

// Watch source selection → auto-scan files
watch(selectedSource, async (name) => {
  if (!name) {
    ruleFiles.value = []
    return
  }
  loadingFiles.value = true
  try {
    const resp = await apiPost<{ files: Array<{ name: string; path: string }> }>(
      '/rules/scan-by-source',
      { source_name: name },
    )
    if (resp.ok && resp.data?.files) {
      ruleFiles.value = resp.data.files.map((f) => ({
        name: f.name,
        path: f.path,
        checked: true,
        expanded: false,
        loading: false,
        error: '',
        detail: null,
      }))
      // Auto-restore aggregated if available
      await autoRestoreAggregated()
    }
  } catch {
    // Silently handle
  } finally {
    loadingFiles.value = false
  }
})

async function loadFileDetail(file: RuleFileItem): Promise<void> {
  if (file.detail || file.loading) return
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

// ── Expand / collapse ──────────────────────────────────────────────────

async function toggleExpand(file: RuleFileItem) {
  if (file.expanded) {
    file.expanded = false
    return
  }
  if (!file.detail) await loadFileDetail(file)
  file.expanded = true
}

// ── Auto-restore aggregated rules if hash matches ──────────────────────

async function autoRestoreAggregated() {
  if (ruleFiles.value.length === 0) return

  // Restore aggregated result from workspace API
  try {
    const workspaceId = route.params.workspaceId as string
    const resp = await apiGet<Record<string, unknown>>(`/workspace/${workspaceId}/rules/aggregated`)
    if (resp.ok && resp.data) {
      // Only restore if the store doesn't already have data
      const store = useForestStore()
      if (!store.aggregatedRuleSet) {
        store.aggregatedRuleSet = resp.data as Record<string, unknown>
      }
      savedCount.value = ruleFiles.value.filter(f => f.checked).length
    }
  } catch { /* silent */ }
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
    // 1. Aggregate rules via workspace API
    const workspaceId = route.params.workspaceId as string
    const aggResp = await apiPost<Record<string, unknown>>(`/workspace/${workspaceId}/rules/aggregate`, {
      paths: selectedPaths,
    })

    if (!aggResp.ok) {
      // FastAPI 422 returns { detail: [...] } not { errors: [...] }
      const rawResp = aggResp as unknown as Record<string, unknown>
      const details = rawResp.detail as Array<{ msg: string }> | undefined
      const errs = (aggResp.errors as string[] | undefined) || details?.map((d: { msg: string }) => d.msg)
      const raw = (errs && errs.length > 0) ? errs.join('；') : '聚合规则失败'
      const desc = describeErrors(errs)
      const msg = desc ? `${desc}（${raw}）` : raw
      ElMessage.error({ message: msg, duration: 8000 })
      saving.value = false
      return
    }

    // Store aggregated rule set in memory for downstream pages.
    // Backend workspace API handles metadata persistence.
    if (aggResp.data) {
      const payload = aggResp.data as Record<string, unknown>
      const { output_path: _op, aggregated_hash: _ah, aggregated_at: _aa, rule_count: _rc, ...ruleSet } = payload
      // Keep only rule-set shape in memory (without metadata fields)
      forestStore.aggregatedRuleSet = ruleSet
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

/** Translate backend error codes to human-readable Chinese descriptions. */
function describeErrors(errors: string[] | undefined): string | null {
  if (!errors || errors.length === 0) return null
  const descriptions = errors
    .map((msg) => {
      const desc = getDescription(msg)
      if (desc) return desc
      // Extract code from message for the fallback
      const codeMatch = msg.match(/^(E_\w+)/)
      return codeMatch ? msg : msg
    })
    .filter(Boolean)
  return descriptions.join('；')
}
</script>

<style scoped>
.rules-overview-page {
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

.source-hint {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}

.hint-text {
  color: #909399;
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

.file-name-row {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  overflow-x: auto;
  scrollbar-width: none;
  min-width: 0;
}
.file-name-row::-webkit-scrollbar { display: none; }
.file-display-name {
  font-weight: 700;
  font-size: 14px;
  color: #303133;
}
.file-path-name {
  font-weight: 400;
  font-size: 12px;
  color: #999;
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
  align-items: center;
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
