<template>
  <div class="compute-prep-page gui-page">
    <h2>🧮 计算准备</h2>
    <!-- ── Empty state: no rules selected ────────────────────────────── -->
    <template v-if="noRulesSelected">
      <el-card shadow="never">
        <el-empty description="请先在规则概览选择规则">
          <el-button size="small" text class="subtle-link" @click="$router.push(`/workspace/${$route.params.workspaceId}/rules`)">前往规则概览</el-button>
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
            :loading="computing"
            :disabled="computing"
            @click="startComputeAndView"
          >
            🚀 计算查看
          </el-button>
          <el-button
            type="warning"
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
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiPost, apiGet } from '../api/transport'
import { streamSse } from '../api/transport'
import { useAppStore } from '../stores/app'
import { useForestStore } from '../stores/forest'

// ── Router ────────────────────────────────────────────────────────────────
const router = useRouter()
const route = useRoute()
const workspaceId = computed(() => route.params.workspaceId as string)
const appStore = useAppStore()


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
  if (workspaceId.value) {
    appStore.setCurrentWorkspaceId(workspaceId.value)
  }
  await loadData()
})

async function tryRestoreAggregatedRuleSetFromBackend(): Promise<Record<string, unknown> | null> {
  const workspaceId = route.params.workspaceId as string
  if (!workspaceId) return null

  const resp = await apiGet<Record<string, unknown>>(`/workspace/${workspaceId}/rules/aggregated`)
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

  // 4. Get selected database

  // 5. Fetch affected entries
  try {
    const entriesResp = await apiPost<AffectedEntriesData>('/rules/affected-entries', {
      aggregated_rule_set: aggregatedRuleSet || undefined,
      database_name: "default",
    })

    if (!entriesResp.ok || !entriesResp.data) {
      loadingFailed.value = true
      loadingErrorMessage.value = entriesResp.errors?.join('; ') || '无法加载受影响的条目'
      return
    }

    const data = entriesResp.data

    // Populate libraries with frontend state (default unchecked — recalc after decisions)
    libraries.value = data.libraries.map((lib) => ({
      ...lib,
      _checked: false,
      _indeterminate: false,
      _visible: true,
    }))

    // Restore library visibility from uiState (keyed by library.index)
    const savedVis = appStore.loadUiStateFor<Record<number, boolean>>(`computePrep.visibility.${workspaceId.value}`)
    if (savedVis) {
      for (const lib of libraries.value) {
        if (savedVis[lib.index] !== undefined) {
          lib._visible = savedVis[lib.index]
        }
      }
    }
    // Populate games with frontend state (default unchecked — restored from decisions below)
    games.value = data.games.map((g) => ({
      ...g,
      _checked: false,
    }))

    // Populate mods with frontend state (default unchecked — restored from decisions below)
    mods.value = data.mods.map((m) => ({
      ...m,
      _checked: false,
    }))

    // Load decisions from workspace API and restore checkbox state
    try {
      const decisionsResp = await apiGet<{ managed_entries: { game: Record<string, string[]>; mod: Record<string, string[]> } }>(
        `/workspace/${workspaceId.value}/decisions/load`
      )
      if (decisionsResp.ok && decisionsResp.data?.managed_entries) {
        const { game: gameKept, mod: modKept } = decisionsResp.data.managed_entries
        const hasGameKept = gameKept && Object.keys(gameKept).length > 0
        const hasModKept = modKept && Object.keys(modKept).length > 0

        if (hasGameKept) {
          for (const g of games.value) {
            const kept = gameKept[g.appid]
            g._checked = kept === undefined || kept.includes(g.basepath)
          }
        } else {
          // No game decisions → default all checked
          for (const g of games.value) g._checked = true
        }

        if (hasModKept) {
          for (const m of mods.value) {
            const kept = modKept[m.mixed_id]
            m._checked = kept === undefined || kept.includes(m.path)
          }
        } else {
          // No mod decisions → default all checked
          for (const m of mods.value) m._checked = true
        }
      } else {
        // No decisions yet → default all checked
        for (const g of games.value) g._checked = true
        for (const m of mods.value) m._checked = true
      }
    } catch {
      // Decisions API not available → default all checked
      for (const g of games.value) g._checked = true
      for (const m of mods.value) m._checked = true
    }

    // Load decisions from workspace API and restore checkbox state
    try {
      const decisionsResp = await apiGet<{ managed_entries: { game: Record<string, string[]>; mod: Record<string, string[]> } }>(
        `/workspace/${workspaceId.value}/decisions/load`
      )
      if (decisionsResp.ok && decisionsResp.data?.managed_entries) {
        const { game: gameKept, mod: modKept } = decisionsResp.data.managed_entries
        if (gameKept) {
          for (const g of games.value) {
            const kept = gameKept[g.appid]
            if (kept !== undefined) {
              g._checked = kept.includes(g.basepath)
            }
          }
        }
        if (modKept) {
          for (const m of mods.value) {
            const kept = modKept[m.mixed_id]
            if (kept !== undefined) {
              m._checked = kept.includes(m.path)
            }
          }
        }
      }
    } catch {
      // Decisions API not available — all entries remain checked (default)
    }

    // Recalculate library checkbox states after decisions restored
    for (const lib of libraries.value) {
      recalcLibraryState(lib.index)
    }

    // Check if workspace already has computed results
    try {
      const mappingResp = await apiGet<Record<string, unknown>>(
        `/workspace/${workspaceId.value}/forest/mapping`
      )
      if (mappingResp.ok && mappingResp.data && (mappingResp.data.trees || mappingResp.data.final_mapping)) {
        canViewResults.value = true
      }
    } catch { /* ignore — no results yet */ }

    // Check if there are existing results to enable "View Results" button
    if (forestStore.trees.length > 0 || forestStore.finalMapping.length > 0) {
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

  // Persist visibility state via saveUiState
  const vis: Record<number, boolean> = {}
  for (const l of libraries.value) {
    vis[l.index] = l._visible
  }
  appStore.saveUiStateFor(`computePrep.visibility.${workspaceId.value}`, vis)
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

/**
 * Core compute logic shared by "开始计算" and "计算并查看".
 * Returns true on success.
 */
async function doCompute(): Promise<boolean> {
  computing.value = true
  computeMessage.value = ''
  computeSuccess.value = false

  const forestStore = useForestStore()
  const managedEntries = buildManagedEntries()
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
    return false
  }

  try {
    const wid = workspaceId.value
    await streamSse(`/workspace/${wid}/pipeline/compute`, {
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

          // Populate forest store for visualization
          forestStore.trees = (result.data.trees as any[]) || []
          forestStore.finalMapping = (result.data.final_mapping as any[]) || []
        }
        computing.value = false
      },
      onError(msg: string) {
        computeMessage.value = msg
        computing.value = false
      },
    })

    // Save decisions via workspace API
    await apiPost(`/workspace/${wid}/decisions/save`, {
      managed_entries: managedEntries,
    })

    return true
  } catch {
    computeMessage.value = '网络错误：计算请求失败'
    computeSuccess.value = false
    return false
  } finally {
    computing.value = false
  }
}

/** "▶️ 开始计算" — compute and stay on page */
async function startCompute() {
  await doCompute()
}

/** "🚀 计算并查看" — compute then navigate to forest visualization */
async function startComputeAndView() {
  const ok = await doCompute()
  if (ok) {
    router.push(`/workspace/${workspaceId.value}/forest`)
  }
}

// ── View results ──────────────────────────────────────────────────────────

function viewResults() {
  router.push(`/workspace/${workspaceId.value}/forest`)
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
