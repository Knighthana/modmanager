<template>
  <div class="datasource-page gui-page">
    <h2>{{ STR.dataSourcePage.title }}</h2>

    <!-- Mode + Settings -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <span>{{ STR.dataSourcePage.discoveryCard }}</span>
      </template>
      <el-form label-width="140px">
        <el-form-item :label="STR.dataSourcePage.discoveryMode">
          <el-radio-group v-model="store.discoveryMode">
            <el-radio value="all">{{ STR.dataSourcePage.modeAll }}</el-radio>
            <el-radio value="auto">{{ STR.dataSourcePage.modeAuto }}</el-radio>
            <el-radio value="manual">{{ STR.dataSourcePage.modeManual }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="STR.dataSourcePage.greedyParsing">
          <el-switch v-model="store.greedyParsing" />
        </el-form-item>
        <el-form-item
          v-if="store.discoveryMode === 'manual' || store.discoveryMode === 'all'"
          :label="STR.dataSourcePage.manualPathLabel"
        >
          <div style="width: 100%;">
            <el-table :data="store.manualPaths" border stripe size="small" style="width: 100%;">
              <el-table-column label="路径">
                <template #default="{ row, $index }">
                  <template v-if="editingManualPathIdx !== $index">
                    <code
                      style="cursor: pointer; font-size: 13px;"
                      @click="startEditManualPath($index, row)"
                    >{{ row }}</code>
                  </template>
                  <template v-else>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <el-input
                        v-model="editingManualPathVal"
                        size="small"
                        @keyup.enter="confirmEditManualPath($index)"
                        @keyup.esc="cancelEditManualPath"
                      />
                      <el-button size="small" type="primary" @click="confirmEditManualPath($index)">确定</el-button>
                      <el-button size="small" @click="cancelEditManualPath">取消</el-button>
                    </div>
                  </template>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-popconfirm title="确认删除？" @confirm="removeManualPath($index)">
                    <template #reference>
                      <el-button size="small" type="danger" text>删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
              <template #append>
                <div style="padding: 4px 0;">
                  <template v-if="!isAddingManualPath">
                    <span
                      style="cursor: pointer; font-size: 13px; color: #409eff;"
                      @click="isAddingManualPath = true"
                    >➕ 添加路径</span>
                  </template>
                  <template v-else>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <el-input
                        v-model="newManualPath"
                        :placeholder="STR.dataSourcePage.manualPathPlaceholder"
                        size="small"
                        @keyup.enter="confirmAddManualPath"
                        @keyup.esc="cancelAddManualPath"
                      />
                      <el-button size="small" type="primary" @click="confirmAddManualPath">确定</el-button>
                      <el-button size="small" @click="cancelAddManualPath">取消</el-button>
                    </div>
                  </template>
                </div>
              </template>
            </el-table>
            <div style="font-size:12px;color:#999;margin-top:4px;">
              {{ STR.dataSourcePage.manualPathHint }}
            </div>
          </div>
        </el-form-item>
        <el-form-item label="目标数据库">
          <DatabaseSelector ref="databaseSelectorRef" :showDecisionsTag="false" />
        </el-form-item>
        <el-form-item>
          <el-button
            type="warning"
            :loading="store.isScanning"
            :disabled="store.isScanning || isDiscoverDisabled"
            @click="onScan"
          >
            {{ store.isScanning ? STR.dataSourcePage.scanning : STR.dataSourcePage.scanBtn }}
          </el-button>
          <el-button
            type="primary"
            size="default"
            :disabled="!store.lastResult"
            @click="onConfirm"
          >
            {{ STR.dataSourcePage.confirmToRulesOverview }}
          </el-button>
          <span v-if="isDiscoverDisabled" style="margin-left: 8px; font-size: 12px; color: #999;">
            {{ STR.dataSourcePage.manualPathRequired }}
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 扫描结果 -->
    <template v-if="store.libraries.length > 0">
      <!-- 库摘要表 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <span>{{ STR.dataSourcePage.libSummary(store.libraries.length) }}</span>
        </template>
        <el-table :data="store.libraries" border stripe size="small" ref="libTableRef">
          <el-table-column :label="STR.dataSourcePage.colIndex" width="60" type="index" />
          <el-table-column :label="STR.dataSourcePage.colVis" width="70">
            <template #default="{ row }: { row: LibraryRow }">
              <el-button
                v-if="store.libraryVisibility[row.index] !== false"
                size="small"
                type="success"
                @click="store.setLibraryVisibility(row.index, false)"
              >
                👀
              </el-button>
              <el-button
                v-else
                size="small"
                type="warning"
                @click="store.setLibraryVisibility(row.index, true)"
              >
                🙈
              </el-button>
            </template>
          </el-table-column>
          <el-table-column :label="STR.dataSourcePage.colLibName" width="100">
            <template #default="{ row }: { row: LibraryRow }">
              {{ STR.dataSourcePage.libName(row.index) }}
            </template>
          </el-table-column>
          <el-table-column :label="STR.dataSourcePage.colGameCount" width="80" prop="gameCount" />
          <el-table-column :label="STR.dataSourcePage.colModCount" width="80" prop="modCount" />
          <el-table-column :label="STR.dataSourcePage.colPath" min-width="200" class-name="horizontal-cell-scroll">
            <template #default="{ row }: { row: LibraryRow }">
              <div class="horizontal-cell-scroll">{{ ensureTrailingSlash(row.path) }}</div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 游戏表 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <span>{{ STR.dataSourcePage.gameTable(store.filteredGames.length) }}</span>
        </template>
        <el-table :data="store.filteredGames" border stripe size="small" ref="gameTableRef">
          <el-table-column :label="STR.dataSourcePage.colIndex" width="60" type="index" />
          <el-table-column :label="STR.dataSourcePage.colVis" width="70">
            <template #default="{ row }: { row: GameRow }">
              <el-button
                v-if="store.gameVisibility[row.index] !== false"
                size="small"
                type="success"
                @click="store.setGameVisibility(row.index, false)"
              >
                👀
              </el-button>
              <el-button
                v-else
                size="small"
                type="warning"
                @click="store.setGameVisibility(row.index, true)"
              >
                🙈
              </el-button>
            </template>
          </el-table-column>
          <el-table-column :label="STR.dataSourcePage.colAppid" width="90" prop="appid" />
          <el-table-column :label="STR.dataSourcePage.colName" min-width="180" prop="name" show-overflow-tooltip />
          <el-table-column :label="STR.dataSourcePage.colModCount" width="80">
            <template #default="{ row }: { row: GameRow }">
              <el-button
                link
                type="primary"
                @click="scrollToFirstMod(row)"
              >
                {{ row.modCount }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column :label="STR.dataSourcePage.colBelongingLib" width="80">
            <template #default="{ row }: { row: GameRow }">
              <el-button
                link
                type="primary"
                @click="scrollToLibrary(row.libraryIndex)"
              >
                {{ STR.dataSourcePage.libName(row.libraryIndex) }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column :label="STR.dataSourcePage.colPath" min-width="200" class-name="horizontal-cell-scroll">
            <template #default="{ row }: { row: GameRow }">
              <div class="horizontal-cell-scroll">{{ ensureTrailingSlash(row.basepath) }}</div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- MOD 表 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <span>{{ STR.dataSourcePage.modTable(store.filteredMods.length) }}</span>
        </template>
        <el-table :data="store.filteredMods" border stripe size="small" ref="modTableRef">
          <el-table-column :label="STR.dataSourcePage.colIndex" width="60" type="index" />
          <el-table-column :label="STR.dataSourcePage.colModId" width="120" prop="modid" show-overflow-tooltip />
          <el-table-column :label="STR.dataSourcePage.colName" min-width="180" prop="name" show-overflow-tooltip />
          <el-table-column :label="STR.dataSourcePage.colBelongingAppid" width="100">
            <template #default="{ row }: { row: ModRow }">
              <el-button
                link
                type="primary"
                @click="scrollToGame(row.gameIndex)"
              >
                {{ row.appid }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column :label="STR.dataSourcePage.colBelongingLib" width="80">
            <template #default="{ row }: { row: ModRow }">
              <el-button
                link
                type="primary"
                @click="scrollToLibrary(row.libraryIndex)"
              >
                {{ STR.dataSourcePage.libName(row.libraryIndex) }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column :label="STR.dataSourcePage.colPath" min-width="200" class-name="horizontal-cell-scroll">
            <template #default="{ row }: { row: ModRow }">
              <div class="horizontal-cell-scroll">{{ ensureTrailingSlash(row.path) }}</div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <!-- 警告区 -->
    <div v-if="store.warnings.length > 0" style="margin-bottom: 16px;">
      <el-alert
        :title="STR.dataSourcePage.scanWarning"
        type="warning"
        :closable="false"
        show-icon
      >
        <template #default>
          <ul style="margin: 4px 0; padding-left: 20px;">
            <li v-for="(w, i) in store.warnings" :key="'w-' + i">
              {{ w }}
            </li>
          </ul>
        </template>
      </el-alert>
    </div>

    <!-- 扫描错误（E_DUPLICATE 等）点击弹出排障指南 -->
    <div v-if="store.errors.length > 0" style="margin-top: 12px;">
      <el-alert
        v-for="(err, idx) in store.errors"
        :key="'err-'+idx"
        :title="err"
        type="error"
        show-icon
        :closable="false"
        style="margin-bottom: 4px; cursor: pointer;"
        @click="(e: MouseEvent) => onErrorPopup(err, e)"
      />
    </div>

    <!-- 错误区（逐条平铺） -->
    <div v-if="saveErrors.length > 0" style="margin-bottom: 16px;">
      <el-alert
        title="保存校验失败"
        type="error"
        :closable="false"
        show-icon
      >
        <template #default>
          <ul style="margin: 4px 0; padding-left: 20px;">
            <li v-for="(e, i) in saveErrors" :key="'e-' + i">
              {{ e }}
            </li>
          </ul>
        </template>
      </el-alert>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useDataSourceStore } from '../stores/datasource'
import { useForestStore } from '../stores/forest'
import { apiPost } from '../api/client'
import { loadUiState, saveUiState, migrateOldWorkspace } from '../utils/persistence'
import { scrollintotabitem } from '../utils/scroll'
import { ensureTrailingSlash } from '../utils/paths'
import { STR } from '../locales/zh-CN'
import type { DiscoverMode, LibraryRow, GameRow, ModRow } from '../types'
import { showPopup } from '../utils/notify'
import { getDescription, extractCode } from '../utils/errorCodes'
import DatabaseSelector from '../components/DatabaseSelector.vue'

const store = useDataSourceStore()
const forestStore = useForestStore()
const router = useRouter()

const databaseSelectorRef = ref<InstanceType<typeof DatabaseSelector> | null>(null)
const libTableRef = ref<any>(null)
const gameTableRef = ref<any>(null)
const modTableRef = ref<any>(null)

// ── manual path add state ──
const newManualPath = ref('')

// ── manual path inline edit state ──
const editingManualPathIdx = ref(-1)
const editingManualPathVal = ref('')
const isAddingManualPath = ref(false)

// ── local managed state (independent of store, not persisted) ──
const localManagedGames = reactive<Record<string, boolean>>({})
const localManagedMods = reactive<Record<string, boolean>>({})

// ── save state ──
const isSaving = ref(false)
const saveErrors = ref<string[]>([])

// ── initialize local managed from store ──
function initLocalManaged() {
  // Clear and re-initialize from store.games
  for (const key of Object.keys(localManagedGames)) {
    delete localManagedGames[key]
  }
  for (const g of store.games) {
    localManagedGames[`game-${g.index}`] = g.managed ?? false
  }

  for (const key of Object.keys(localManagedMods)) {
    delete localManagedMods[key]
  }
  for (const m of store.mods) {
    localManagedMods[`mod-${m.index}`] = m.managed ?? false
  }
}

watch(
  [() => store.games, () => store.mods],
  () => { initLocalManaged() },
  { immediate: true, deep: true },
)

// ── radio change handlers ──
function onGameManagedChange(row: GameRow) {
  // Set all games with same appid to false, then current to true
  for (const g of store.games) {
    if (g.appid === row.appid) {
      localManagedGames[`game-${g.index}`] = false
    }
  }
  localManagedGames[`game-${row.index}`] = true
}

function onModManagedChange(row: ModRow) {
  const mixedId = `${row.appid}:${row.modid}`
  // Set all mods with same mixed_id to false, then current to true
  for (const m of store.mods) {
    if (`${m.appid}:${m.modid}` === mixedId) {
      localManagedMods[`mod-${m.index}`] = false
    }
  }
  localManagedMods[`mod-${row.index}`] = true
}

// ── error popup helper ──
function onErrorPopup(errMsg: string, event: MouseEvent) {
  const desc = getDescription(errMsg) || errMsg
  showPopup(desc, event.target as HTMLElement, event)
}

// ── shared save logic ──
async function doSave(): Promise<boolean> {
  if (!store.lastResult) return false
  saveErrors.value = []
  isSaving.value = true

  // Build save payload: clone lastResult, apply local managed states
  const db = JSON.parse(JSON.stringify(store.lastResult)) as Record<string, unknown>

  // Apply game managed
  const gameArr = (db.game as Array<Record<string, unknown>>) || []
  for (let i = 0; i < gameArr.length; i++) {
    const key = `game-${i}`
    if (key in localManagedGames) {
      gameArr[i].managed = localManagedGames[key]
    }
  }

  // Apply mod managed
  const modArr = (db.mod as Array<Record<string, unknown>>) || []
  for (let i = 0; i < modArr.length; i++) {
    const key = `mod-${i}`
    if (key in localManagedMods) {
      modArr[i].managed = localManagedMods[key]
    }
  }

  // Get selected database name
  const selectedDb = databaseSelectorRef.value?.selectedDatabase ?? 'default'

  try {
    const resp = await apiPost('/database/save', {
      database: db,
      database_name: selectedDb,
    })

    if (resp.ok) {
      // Use the cleaned database returned by the backend
      const savedDb = (resp.data as { database: Record<string, unknown> })?.database || db

      // Update datasource store so managed values are reflected in local state
      store.updateDatabase(savedDb)

      // Persist selected database in uiState
      const ds = loadUiState<Record<string, unknown>>('datasource') ?? {}
      saveUiState('datasource', { ...ds, lastDatabase: selectedDb })

      if (!forestStore.userConfig) {
        await forestStore.loadConfig()
      }
      return true
    } else {
      saveErrors.value = resp.errors || ['保存失败']
      return false
    }
  } catch (err) {
    saveErrors.value = [`保存请求异常: ${err}`]
    return false
  } finally {
    isSaving.value = false
  }
}

// ── save only (no navigation) ──
// ── confirm & navigate to rules overview ──
async function onConfirm() {
  const ok = await doSave()
  if (ok) {
    router.push('/rules-overview')
  }
}

const isDiscoverDisabled = computed(() => {
  if (store.discoveryMode === 'manual') {
    return store.manualPaths.length === 0
  }
  return false
})

// 恢复 UI 状态（仅表单输入 + 可见性开关，不含扫描结果）
function loadUiStateFromStorage() {
  const ds = loadUiState<{
    discoveryMode?: string
    manualPaths?: string[]
    greedyParsing?: boolean
    libraryVisibility?: Record<number, boolean>
    gameVisibility?: Record<number, boolean>
  }>('datasource')
  if (!ds) return
  if (ds.discoveryMode) store.discoveryMode = ds.discoveryMode as DiscoverMode
  if (ds.manualPaths) store.manualPaths = ds.manualPaths
  if (ds.greedyParsing !== undefined) store.greedyParsing = ds.greedyParsing
  if (ds.libraryVisibility) store.libraryVisibility = ds.libraryVisibility
  if (ds.gameVisibility) store.gameVisibility = ds.gameVisibility
}

// 保存 UI 状态（仅表单输入 + 可见性开关）
function saveUiStateToStorage() {
  saveUiState('datasource', {
    discoveryMode: store.discoveryMode,
    manualPaths: [...store.manualPaths],
    greedyParsing: store.greedyParsing,
    libraryVisibility: { ...store.libraryVisibility },
    gameVisibility: { ...store.gameVisibility },
  })
}

onMounted(async () => {
  migrateOldWorkspace()
  loadUiStateFromStorage()

  // Auto-load last database from uiState
  const lastDb = (loadUiState<Record<string, unknown>>('datasource')?.lastDatabase as string | undefined)
  if (lastDb) {
    try {
      const resp = await apiPost<{ database: Record<string, unknown> }>(
        '/database/read',
        { database_name: lastDb },
      )
      if (resp.ok && resp.data) {
          store.updateDatabase(resp.data as Record<string, unknown>)
      }
    } catch {
      // 静默失败——用户可以手动扫描
    }
  }
})

onBeforeUnmount(() => {
  saveUiStateToStorage()
})

async function onScan() {
  saveUiStateToStorage()
  const selectedDb = databaseSelectorRef.value?.selectedDatabase ?? 'default'
  await store.scan(selectedDb)
}

// ── manual path management ──

function confirmAddManualPath() {
  const val = newManualPath.value.trim()
  if (val) {
    store.manualPaths.push(val)
  }
  newManualPath.value = ''
  isAddingManualPath.value = false
}

function cancelAddManualPath() {
  isAddingManualPath.value = false
  newManualPath.value = ''
}

// ── manual path inline edit ──

function startEditManualPath(idx: number, val: string) {
  if (editingManualPathIdx.value !== -1) cancelEditManualPath()
  if (isAddingManualPath.value) cancelAddManualPath()
  editingManualPathIdx.value = idx
  editingManualPathVal.value = val
}

function confirmEditManualPath(idx: number) {
  const val = editingManualPathVal.value.trim()
  if (val) {
    store.manualPaths[idx] = val
  }
  editingManualPathIdx.value = -1
  editingManualPathVal.value = ''
}

function cancelEditManualPath() {
  editingManualPathIdx.value = -1
  editingManualPathVal.value = ''
}

function removeManualPath(idx: number) {
  store.manualPaths.splice(idx, 1)
}

function scrollToLibrary(libraryIndex: number) {
  const table = libTableRef.value
  if (!table) return
  const rows = (table.$el as HTMLElement).querySelectorAll('.el-table__body-wrapper tbody tr')
  const targetRow = rows[libraryIndex] as HTMLElement | undefined
  scrollintotabitem(targetRow ?? null)
}

function scrollToGame(gameIndex: number) {
  const table = gameTableRef.value
  if (!table) return
  const rows = (table.$el as HTMLElement).querySelectorAll('.el-table__body-wrapper tbody tr')
  const targetRow = rows[gameIndex] as HTMLElement | undefined
  scrollintotabitem(targetRow ?? null)
}

function scrollToFirstMod(game: GameRow) {
  const firstMod = store.mods.find(
    m => m.appid === game.appid && m.gameIndex === game.index,
  )
  if (!firstMod) return
  const table = modTableRef.value
  if (!table) return
  const rows = (table.$el as HTMLElement).querySelectorAll('.el-table__body-wrapper tbody tr')
  const targetRow = rows[firstMod.index] as HTMLElement | undefined
  scrollintotabitem(targetRow ?? null)
}
</script>

<style scoped>
.horizontal-cell-scroll {
  white-space: nowrap;
  overflow-x: auto;
  scrollbar-width: none;
}
.horizontal-cell-scroll::-webkit-scrollbar {
  display: none;
}

.datasource-page {
  margin: 0 auto;
  padding: 16px 24px;
}
</style>
