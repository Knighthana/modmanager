<template>
  <div class="compute-prep-page gui-page">
    <h2>🧮 计算准备</h2>
    <!-- ── Empty state: no rules selected ────────────────────────────── -->
    <template v-if="noRulesSelected">
      <el-card shadow="never">
        <el-empty description="请先在规则概览选择规则">
          <el-button size="small" text @click="$router.push('/rules-overview')">前往规则概览</el-button>
        </el-empty>
      </el-card>
    </template>

    <!-- ── Empty state: rules cover no entries ──────────────────────── -->
    <template v-else-if="loadingFailed">
      <el-card shadow="never">
        <el-empty :description="loadingErrorMessage" />
      </el-card>
    </template>

    <!-- ── Main content ─────────────────────────────────────────────── -->
    <template v-else>
      <!-- DatabaseSelector -->
      <div style="margin-bottom: 16px;">
        <DatabaseSelector ref="databaseSelectorRef" />
      </div>

      <!-- Top action bar -->
      <div class="action-bar">
        <div class="action-buttons">
          <el-button
            type="primary"
            :loading="computing"
            :disabled="computing"
            @click="startCompute"
          >
            ▶️ 开始计算
          </el-button>
          <el-button
            type="success"
            :disabled="!canViewResults"
            @click="viewResults"
          >
            👁️ 查看结果
          </el-button>
        </div>
        <div v-if="computeMessage" class="compute-result-text" :class="{ 'compute-success': computeSuccess }">
          {{ computeMessage }}
        </div>
      </div>

      <div v-if="summaryText" class="summary-line">
        {{ summaryText }}
      </div>

      <!-- ── Library table ──────────────────────────────────────────── -->
      <div class="section">
        <div class="section-title">▶ 库</div>
        <el-table :data="libraries" border stripe size="small" class="data-table">
          <el-table-column label="选中" width="60" align="center">
            <template #default="{ row }">
              <el-checkbox
                :model-value="row._checked"
                :indeterminate="row._indeterminate"
                @change="(val: string | number | boolean) => toggleLibrary(row.index, !!val)"
              />
            </template>
          </el-table-column>
          <el-table-column label="序号" width="56" align="center">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column label="可见" width="70" align="center">
            <template #default="{ row }">
              <el-button
                v-if="row._visible"
                size="small"
                type="success"
                @click="toggleLibraryVisibility(row.index)"
              >
                👀
              </el-button>
              <el-button
                v-else
                size="small"
                type="warning"
                @click="toggleLibraryVisibility(row.index)"
              >
                🙈
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="游戏" width="60" align="center" prop="game_count" />
          <el-table-column label="MOD" width="60" align="center" prop="mod_count" />
          <el-table-column label="路径" min-width="300">
            <template #default="{ row }">
              <div class="path-cell">{{ row.path }}</div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- ── Game table ─────────────────────────────────────────────── -->
      <div class="section">
        <div class="section-title">▶ 游戏</div>
        <el-table
          :data="filteredGames"
          border
          stripe
          size="small"
          class="data-table"
          :row-class-name="gameRowClass"
        >
          <el-table-column label="选中" width="60" align="center">
            <template #default="{ row }">
              <el-checkbox v-model="row._checked" @change="() => onChildChange(row.libraryIndex)" />
            </template>
          </el-table-column>
          <el-table-column label="序号" width="56" align="center">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column label="appid" width="100" prop="appid" />
          <el-table-column label="名称" min-width="180" prop="name" />
          <el-table-column label="路径" min-width="320">
            <template #default="{ row }">
              <div class="path-cell scroll-x">{{ row.basepath }}</div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- ── MOD table ──────────────────────────────────────────────── -->
      <div class="section">
        <div class="section-title">▶ MOD</div>
        <el-table
          :data="filteredMods"
          border
          stripe
          size="small"
          class="data-table"
          :row-class-name="modRowClass"
        >
          <el-table-column label="选中" width="60" align="center">
            <template #default="{ row }">
              <el-checkbox v-model="row._checked" @change="() => onChildChange(row.libraryIndex)" />
            </template>
          </el-table-column>
          <el-table-column label="序号" width="56" align="center">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column label="mixed_id" width="200" prop="mixed_id" />
          <el-table-column label="名称" width="120" prop="nickname" />
          <el-table-column label="路径" min-width="320">
            <template #default="{ row }">
              <div class="path-cell scroll-x">{{ row.path }}</div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiPost } from '../api/client'
import { streamSse } from '../api/sse'
import { loadWorkspace, saveWorkspace } from '../utils/persistence'
import { hashRuleSet } from '../utils/hash'
import { useForestStore } from '../stores/forest'
import DatabaseSelector from '../components/DatabaseSelector.vue'

// ── Router ────────────────────────────────────────────────────────────────
const router = useRouter()

const databaseSelectorRef = ref<InstanceType<typeof DatabaseSelector> | null>(null)

// ── Types ──────────────────────────────────────────────────────────────────

interface AffectedLibrary {
  index: number
  path: string
  game_count: number
  mod_count: number
  // frontend-only reactive state
  _checked: boolean
  _indeterminate: boolean
  _visible: boolean
}

interface AffectedGame {
  appid: string
  name: string
  basepath: string
  libraryIndex: number
  has_duplicate: boolean
  // frontend-only reactive state
  _checked: boolean
}

interface AffectedMod {
  mixed_id: string
  nickname: string
  path: string
  libraryIndex: number
  gameIndex: number
  has_duplicate: boolean
  // frontend-only reactive state
  _checked: boolean
}

interface AffectedEntriesData {
  libraries: AffectedLibrary[]
  games: AffectedGame[]
  mods: AffectedMod[]
}

// ── Reactive state ─────────────────────────────────────────────────────────

const libraries = ref<AffectedLibrary[]>([])
const games = ref<AffectedGame[]>([])
const mods = ref<AffectedMod[]>([])
const noRulesSelected = ref(false)
const loadingFailed = ref(false)
const loadingErrorMessage = ref('')
const computing = ref(false)
const computeMessage = ref('')
const computeSuccess = ref(false)
const canViewResults = ref(false)

// ── Computed: filtered games/mods by library visibility ──────────────────

const filteredGames = computed(() =>
  games.value.filter((g) => {
    const lib = libraries.value.find((l) => l.index === g.libraryIndex)
    return lib ? lib._visible : true
  }),
)

const filteredMods = computed(() =>
  mods.value.filter((m) => {
    const lib = libraries.value.find((l) => l.index === m.libraryIndex)
    return lib ? lib._visible : true
  }),
)

// ── Computed: summary text ──────────────────────────────────────────────

const summaryText = computed(() => {
  if (libraries.value.length === 0) return ''
  const libCount = libraries.value.length

  // Count unique games and duplicates
  const gameAppids = games.value.map((g) => g.appid)
  const uniqueGameAppids = [...new Set(gameAppids)]
  const duplicateGameAppids = uniqueGameAppids.filter(
    (appid) => games.value.filter((g) => g.appid === appid).length > 1,
  )

  // Count unique mods and duplicates
  const modMixedIds = mods.value.map((m) => m.mixed_id)
  const uniqueModMixedIds = [...new Set(modMixedIds)]
  const duplicateModMixedIds = uniqueModMixedIds.filter(
    (mixedId) => mods.value.filter((m) => m.mixed_id === mixedId).length > 1,
  )

  const parts: string[] = []
  parts.push(`覆盖 ${libCount} 个库`)
  parts.push(`${uniqueGameAppids.length} 个游戏 (${duplicateGameAppids.length} 个有多个入口)`)
  parts.push(`${uniqueModMixedIds.length} 个 MOD (${duplicateModMixedIds.length} 个有多个入口)`)

  return parts.join('，')
})

// ── Row class for duplicate highlighting (computed dynamically from visible rows) ──

const duplicateGameAppids = computed(() => {
  const counts: Record<string, number> = {}
  for (const g of filteredGames.value.filter(g => g._checked)) {
    counts[g.appid] = (counts[g.appid] || 0) + 1
  }
  return new Set(Object.keys(counts).filter(k => counts[k] > 1))
})

const duplicateModMixedIds = computed(() => {
  const counts: Record<string, number> = {}
  for (const m of filteredMods.value.filter(m => m._checked)) {
    counts[m.mixed_id] = (counts[m.mixed_id] || 0) + 1
  }
  return new Set(Object.keys(counts).filter(k => counts[k] > 1))
})

function gameRowClass({ row }: { row: AffectedGame }): string {
  if (!row._checked) return ''
  return duplicateGameAppids.value.has(row.appid) ? 'duplicate-row' : ''
}

function modRowClass({ row }: { row: AffectedMod }): string {
  if (!row._checked) return ''
  return duplicateModMixedIds.value.has(row.mixed_id) ? 'duplicate-row' : ''
}

// ── Lifecycle ─────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadData()
})

async function tryRestoreAggregatedRuleSetFromBackend(): Promise<Record<string, unknown> | null> {
  const ws = loadWorkspace()
  const outputPath = ws.aggregatedRuleMeta?.output_path
  if (!outputPath) return null

  const resp = await apiPost<Record<string, unknown>>('/rules/load-aggregated', {
    path: outputPath,
  })
  if (!resp.ok || !resp.data || typeof resp.data !== 'object') {
    return null
  }

  const forestStore = useForestStore()
  forestStore.aggregatedRuleSet = resp.data
  return resp.data
}

// ── Data loading ──────────────────────────────────────────────────────────

async function loadData() {
  // 1. First check for stored aggregated rule set in Pinia store (fresh from RulesOverviewPage)
  const forestStore = useForestStore()
  let aggregatedRuleSet: Record<string, unknown> | null = forestStore.aggregatedRuleSet

  // 2. Fallback: try to restore from backend aggregated output path metadata
  if (!aggregatedRuleSet) {
    try {
      aggregatedRuleSet = await tryRestoreAggregatedRuleSetFromBackend()
    } catch {
      // Keep null and fall through to user-facing message below
    }
  }

  // 3. Fallback: show error if not available
  if (!aggregatedRuleSet) {
    noRulesSelected.value = true
    loadingErrorMessage.value = '未找到可用聚合规则，且无法自动恢复。请返回规则概览页重新聚合。'
    loadingFailed.value = true
    return
  }

  // 4. Hash validation: check if rule set has changed since last compute
  const currentRulesHash = hashRuleSet(aggregatedRuleSet)
  const selectedDb = databaseSelectorRef.value?.selectedDatabase ?? 'default'
  const ws = loadWorkspace()
  const lastSummary = ws.perDatabase?.[selectedDb]?.lastComputeSummary
  const lastRulesHash = lastSummary?.inputs_hash
  const cachedRulesHash = ws.aggregatedRuleMeta?.aggregated_hash || ws.aggregatedRuleHash

  if (lastRulesHash && currentRulesHash !== lastRulesHash) {
    ElMessage.warning('规则集已变更，建议重新计算以获取最新结果')
  } else if (cachedRulesHash && currentRulesHash !== cachedRulesHash) {
    ElMessage.warning('检测到聚合规则缓存已变化，建议重新聚合后再计算')
  }

  // Restore decisions from workspace if available
  const savedDecisions = ws.perDatabase?.[selectedDb]

  // 5. Fetch affected entries
  try {
    const entriesResp = await apiPost<AffectedEntriesData>('/rules/affected-entries', {
      aggregated_rule_set: aggregatedRuleSet || undefined,
      database_name: selectedDb,
    })

    if (!entriesResp.ok || !entriesResp.data) {
      loadingFailed.value = true
      loadingErrorMessage.value = entriesResp.errors?.join('; ') || '无法加载受影响的条目'
      return
    }

    const data = entriesResp.data

    // Populate libraries with frontend state
    libraries.value = data.libraries.map((lib) => ({
      ...lib,
      _checked: true,
      _indeterminate: false,
      _visible: true,
    }))

    // Populate games with frontend state (default checked)
    games.value = data.games.map((g) => ({
      ...g,
      _checked: true,
    }))

    // Populate mods with frontend state (default checked)
    mods.value = data.mods.map((m) => ({
      ...m,
      _checked: true,
    }))

    // Recalculate library tri-state after population
    for (const lib of libraries.value) {
      recalcLibraryState(lib.index)
    }

    // Restore library visibility from workspace.uiState.computePrep.libraryVisibility
    const savedVis = ws.uiState?.computePrep?.libraryVisibility
    if (savedVis) {
      for (const lib of libraries.value) {
        if (savedVis[lib.index] !== undefined) {
          lib._visible = savedVis[lib.index]
        }
      }
    }

    // Check if there are existing results to enable "View Results" button
    if (lastSummary?.timestamp) {
      canViewResults.value = true
    }
  } catch (e) {
    loadingFailed.value = true
    loadingErrorMessage.value = '网络错误：无法加载受影响的条目'
  }
}

// ── Tri-state checkbox logic ──────────────────────────────────────────────

/** Toggle all children of a library */
function toggleLibrary(libIndex: number, newVal: boolean) {
  // Update all games in this library
  for (const g of games.value) {
    if (g.libraryIndex === libIndex) {
      g._checked = newVal
    }
  }
  // Update all mods in this library
  for (const m of mods.value) {
    if (m.libraryIndex === libIndex) {
      m._checked = newVal
    }
  }
  // Update library state
  const lib = libraries.value.find((l) => l.index === libIndex)
  if (lib) {
    lib._checked = newVal
    lib._indeterminate = false
  }
}

/** Recalculate a library's checked/indeterminate state based on its children */
function recalcLibraryState(libIndex: number) {
  const lib = libraries.value.find((l) => l.index === libIndex)
  if (!lib) return

  const childGames = games.value.filter((g) => g.libraryIndex === libIndex)
  const childMods = mods.value.filter((m) => m.libraryIndex === libIndex)
  const allChildren = [...childGames, ...childMods]

  if (allChildren.length === 0) {
    lib._checked = true
    lib._indeterminate = false
    return
  }

  const allChecked = allChildren.every((c) => c._checked)
  const noneChecked = allChildren.every((c) => !c._checked)

  if (allChecked) {
    lib._checked = true
    lib._indeterminate = false
  } else if (noneChecked) {
    lib._checked = false
    lib._indeterminate = false
  } else {
    lib._checked = false
    lib._indeterminate = true
  }
}

/** Called when any game or mod checkbox changes */
function onChildChange(libIndex: number) {
  recalcLibraryState(libIndex)
}

// ── Library visibility toggle ─────────────────────────────────────────────

function toggleLibraryVisibility(libIndex: number) {
  const lib = libraries.value.find((l) => l.index === libIndex)
  if (!lib) return
  lib._visible = !lib._visible

  // Persist visibility state to workspace.uiState.computePrep.libraryVisibility
  const vis: Record<number, boolean> = {}
  for (const l of libraries.value) {
    vis[l.index] = l._visible
  }
  const ws = loadWorkspace()
  if (!ws.uiState) ws.uiState = {}
  if (!ws.uiState.computePrep) ws.uiState.computePrep = {}
  ws.uiState.computePrep.libraryVisibility = vis
  saveWorkspace(ws)
}

// ── Build managedEntries from checkbox state ──────────────────────────────

function buildManagedEntries(): { game: Record<string, string[]>; mod: Record<string, string[]> } {
  const managedGame: Record<string, string[]> = {}
  const managedMod: Record<string, string[]> = {}

  // Group games by appid
  const gamesByAppid: Record<string, AffectedGame[]> = {}
  for (const g of games.value) {
    if (!gamesByAppid[g.appid]) gamesByAppid[g.appid] = []
    gamesByAppid[g.appid].push(g)
  }

  // For each appid, if user has deselected some, collect kept paths
  for (const [appid, entries] of Object.entries(gamesByAppid)) {
    const kept = entries.filter((g) => g._checked).map((g) => g.basepath)
    if (kept.length < entries.length) {
      // User has deselected some — record the kept ones
      managedGame[appid] = kept
    }
  }

  // Group mods by mixed_id
  const modsByMixedId: Record<string, AffectedMod[]> = {}
  for (const m of mods.value) {
    if (!modsByMixedId[m.mixed_id]) modsByMixedId[m.mixed_id] = []
    modsByMixedId[m.mixed_id].push(m)
  }

  for (const [mixedId, entries] of Object.entries(modsByMixedId)) {
    const kept = entries.filter((m) => m._checked).map((m) => m.path)
    if (kept.length < entries.length) {
      managedMod[mixedId] = kept
    }
  }

  return { game: managedGame, mod: managedMod }
}

// ── Compute action ────────────────────────────────────────────────────────

async function startCompute() {
  computing.value = true
  computeMessage.value = ''
  computeSuccess.value = false

  const forestStore = useForestStore()
  const managedEntries = buildManagedEntries()
  const selectedDb = databaseSelectorRef.value?.selectedDatabase ?? 'default'
  let ruleSet = forestStore.aggregatedRuleSet

  if (!ruleSet) {
    try {
      ruleSet = await tryRestoreAggregatedRuleSetFromBackend()
    } catch {
      ruleSet = null
    }
  }

  if (!ruleSet) {
    computeMessage.value = '缺少聚合规则，请返回规则概览页重新聚合后再计算'
    computeSuccess.value = false
    computing.value = false
    return
  }

  try {
    await streamSse('/pipeline/compute', {
      database_name: selectedDb,
      aggregated_rule_set: ruleSet || undefined,
      managed_entries: managedEntries,
    }, {
      onResult(data: unknown) {
        const result = data as {
          ok: boolean
          data?: {
            trees?: unknown[]
            final_mapping?: unknown[]
            warnings?: string[]
            errors?: string[]
            stats?: Record<string, unknown>
          }
          errors?: string[]
        }
        if (!result.ok || result.errors?.length) {
          computeMessage.value = result.errors?.join('; ') || '计算失败'
          computing.value = false
          return
        }
        if (result.data) {
          const treesCount = Array.isArray(result.data.trees) ? result.data.trees.length : 0
          const mappingCount = Array.isArray(result.data.final_mapping) ? result.data.final_mapping.length : 0
          computeMessage.value = `✅ 计算完成：${treesCount} 棵树，${mappingCount} 个映射`
          computeSuccess.value = true
          canViewResults.value = true

          // Save results to workspace
          const dbName = databaseSelectorRef.value?.selectedDatabase ?? 'default'
          const w1 = loadWorkspace()
          w1.lastDatabase = dbName
          if (!w1.perDatabase[dbName]) {
            w1.perDatabase[dbName] = { lastComputeSummary: null }
          }
          w1.perDatabase[dbName].lastComputeSummary = {
            trees_count: treesCount,
            mapping_count: mappingCount,
            warnings: result.data.warnings ?? [],
            errors: result.data.errors ?? [],
            stats: result.data.stats ?? {},
            inputs_hash: hashRuleSet(ruleSet),
            timestamp: new Date().toISOString(),
          }
          if (w1.aggregatedRuleMeta) {
            w1.aggregatedRuleMeta.aggregated_hash = hashRuleSet(ruleSet)
            w1.aggregatedRuleHash = w1.aggregatedRuleMeta.aggregated_hash
          }
          saveWorkspace(w1)
        }
        computing.value = false
      },
      onError(msg: string) {
        computeMessage.value = msg
        computing.value = false
      },
    })

    // Save decisions to workspace
    const w2 = loadWorkspace()
    w2.lastDatabase = selectedDb
    if (!w2.perDatabase[selectedDb]) {
      w2.perDatabase[selectedDb] = { lastComputeSummary: null }
    }
    w2.perDatabase[selectedDb].managedEntries = managedEntries
    saveWorkspace(w2)
  } catch {
    computeMessage.value = '网络错误：计算请求失败'
    computeSuccess.value = false
  } finally {
    computing.value = false
  }
}

// ── View results ──────────────────────────────────────────────────────────

function viewResults() {
  router.push('/forest')
}
</script>

<style scoped>
.compute-prep-page {
  margin: 0 auto;
  padding: 16px 24px;
}

/* ── Action bar ─────────────────────────────── */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
}

.action-buttons {
  display: flex;
  gap: 12px;
}

.summary-text {
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
}

/* ── Compute message ────────────────────────── */
.compute-result-text {
  padding: 4px 12px;
  border-radius: 4px;
  background: #fef0f0;
  color: #f56c6c;
  font-size: 13px;
}

.compute-result-text.compute-success {
  background: #f0f9eb;
  color: #67c23a;
}

/* ── Section ────────────────────────────────── */
.section {
  margin-bottom: 20px;
}

.section-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
  margin-bottom: 8px;
}

/* ── Tables ─────────────────────────────────── */
.data-table {
  width: 100%;
}

/* ── Path cell ──────────────────────────────── */
.path-cell {
  white-space: nowrap;
  overflow-x: auto;
  scrollbar-width: none;
  font-family: 'Courier New', Courier, monospace;
  font-size: 12px;
}

.path-cell::-webkit-scrollbar {
  display: none;
}

/* ── Duplicate row highlight (soft yellow) ───── */
:deep(.el-table__body tr.duplicate-row > td.el-table__cell) {
  background-color: #fffbe6 !important;
}

:deep(.el-table__body tr.duplicate-row:hover > td.el-table__cell) {
  background-color: #fff5cc !important;
}
</style>
