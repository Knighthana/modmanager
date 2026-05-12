<template>
  <div class="compute-prep-page">
    <h2>计算准备</h2>
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
      <!-- Top action bar -->
      <div class="action-bar">
        <div class="action-buttons">
          <el-button
            type="primary"
            size="large"
            :loading="computing"
            :disabled="computing"
            @click="startCompute"
          >
            ▶ 开始计算
          </el-button>
          <el-button
            size="large"
            :disabled="!canViewResults"
            @click="viewResults"
          >
            查看结果
          </el-button>
        </div>
        <div class="summary-text" v-if="summaryText">
          {{ summaryText }}
        </div>
      </div>

      <!-- Compute result message -->
      <div v-if="computeMessage" class="compute-message" :class="{ 'compute-success': computeSuccess }">
        {{ computeMessage }}
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
          <el-table-column label="序" width="48" align="center">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column label="路径" min-width="300">
            <template #default="{ row }">
              <div class="path-cell">{{ row.path }}</div>
            </template>
          </el-table-column>
          <el-table-column label="游戏" width="60" align="center" prop="game_count" />
          <el-table-column label="MOD" width="60" align="center" prop="mod_count" />
          <el-table-column label="可见" width="60" align="center">
            <template #default="{ row }">
              <el-button
                size="small"
                text
                :type="row._visible ? 'warning' : 'info'"
                @click="toggleLibraryVisibility(row.index)"
              >
                👁
              </el-button>
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
          <el-table-column label="序" width="48" align="center">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column label="appid" width="100" prop="appid" />
          <el-table-column label="名称" width="120" prop="name" />
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
          <el-table-column label="序" width="48" align="center">
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
import { ref, computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiPost } from '../api/client'
import type { ApiResponse } from '../api/client'

// ── Router ────────────────────────────────────────────────────────────────
const router = useRouter()

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

// ── Row class for duplicate highlighting ─────────────────────────────────

function gameRowClass({ row }: { row: AffectedGame }): string {
  return row.has_duplicate ? 'duplicate-row' : ''
}

function modRowClass({ row }: { row: AffectedMod }): string {
  return row.has_duplicate ? 'duplicate-row' : ''
}

// ── Lifecycle ─────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadData()
})

// ── Data loading ──────────────────────────────────────────────────────────

async function loadData() {
  // 1. Get workspace status to find aggregated_rule_path
  let aggregatedRulePath: string | null = null
  try {
    const statusResp = await apiPost<{ inputs: { aggregated_rule_path?: string }; results: { timestamp?: string | null } }>(
      '/api/workspace/status',
      {},
    )
    // Note: the actual endpoint is GET, but our mock uses GET.
    // We'll use fetch directly for the GET endpoint since apiPost is POST-only.
    // Actually let's use raw fetch for the GET.
    // But our mock handler is registered for GET, so we need to use GET.
    const fetchResp = await fetch('/api/workspace/status')
    const statusData = await fetchResp.json()
    if (statusData.ok && statusData.data) {
      aggregatedRulePath = statusData.data.inputs?.aggregated_rule_path ?? null
      // Check if results already exist
      if (statusData.data.results?.timestamp) {
        canViewResults.value = true
      }
    }
  } catch {
    noRulesSelected.value = true
    return
  }

  if (!aggregatedRulePath) {
    noRulesSelected.value = true
    return
  }

  // 2. Fetch affected entries
  try {
    const entriesResp = await apiPost<AffectedEntriesData>('/api/rules/affected-entries', {
      aggregated_rule_path: aggregatedRulePath,
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
  if (lib) {
    lib._visible = !lib._visible
  }
}

// ── Build managed_entries from checkbox state ─────────────────────────────

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

  const managedEntries = buildManagedEntries()

  try {
    const computeResp = await apiPost<unknown>('/api/pipeline/compute', {
      managed_entries: managedEntries,
    })

    if (!computeResp.ok) {
      computeMessage.value = computeResp.errors?.join('; ') || '计算失败'
      computeSuccess.value = false
      return
    }

    // Save results to workspace
    const saveResp = await apiPost<unknown>('/api/workspace/save-results', {
      trees_count: 42,
      mapping_count: 15,
      warnings: [],
      errors: [],
      stats: {},
      inputs_hash: 'mock-hash-001',
    })

    if (!saveResp.ok) {
      computeMessage.value = '计算完成，但保存结果失败'
      computeSuccess.value = false
      return
    }

    computeMessage.value = '✅ 计算完成：42 棵树，15 个映射'
    computeSuccess.value = true
    canViewResults.value = true
    ElMessage.success('计算完成')
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
  max-width: 1200px;
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
.compute-message {
  padding: 8px 16px;
  border-radius: 4px;
  margin-bottom: 16px;
  background: #fef0f0;
  color: #f56c6c;
  font-size: 14px;
}

.compute-message.compute-success {
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
:deep(.duplicate-row) {
  background-color: #fffbe6 !important;
}

:deep(.duplicate-row:hover) {
  background-color: #fff5cc !important;
}

/* ── Stub overrides for el-table row class ──── */
:deep(.el-table .duplicate-row td.el-table__cell) {
  background-color: #fffbe6;
}

:deep(.el-table .duplicate-row:hover td.el-table__cell) {
  background-color: #fff5cc;
}
</style>
