<template>
  <div>
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
        <el-form-item :label="STR.dataSourcePage.workingPathstyle">
          <el-select v-model="store.workingPathstyle" style="width: 200px;">
            <el-option label="auto" value="auto" />
            <el-option label="linux" value="linux" />
            <el-option label="windows" value="windows" />
          </el-select>
        </el-form-item>
        <el-form-item :label="STR.dataSourcePage.greedyParsing">
          <el-switch v-model="store.greedyParsing" />
        </el-form-item>
        <el-form-item :label="STR.dataSourcePage.databaseOutputPath">
          <el-input v-model="store.databaseOutputPath" :placeholder="STR.dataSourcePage.databaseOutputPathPlaceholder" />
        </el-form-item>
        <el-form-item
          v-if="store.discoveryMode === 'manual' || store.discoveryMode === 'all'"
          :label="STR.dataSourcePage.manualPathLabel"
        >
          <el-input
            v-model="store.manualPath"
            :placeholder="STR.dataSourcePage.manualPathPlaceholder"
          />
          <div style="font-size:12px;color:#999;margin-top:4px;">
            {{ STR.dataSourcePage.manualPathHint }}
          </div>
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
        <el-table :data="store.libraries" border stripe size="small">
          <el-table-column :label="STR.dataSourcePage.colIndex" width="60" type="index" />
          <el-table-column :label="STR.dataSourcePage.colVis" width="70">
            <template #default="{ row }: { row: LibraryRow }">
              <el-button
                v-if="store.libraryVisibility[row.index] !== false"
                size="small"
                type="success"
                @click="store.setLibraryVisibility(row.index, false)"
              >
                ✅
              </el-button>
              <el-button
                v-else
                size="small"
                type="warning"
                @click="store.setLibraryVisibility(row.index, true)"
              >
                ❌
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
        <el-table :data="store.filteredGames" border stripe size="small">
          <el-table-column :label="STR.dataSourcePage.colIndex" width="60" type="index" />
          <el-table-column label="[选]" width="50">
            <template #default="{ row }: { row: GameRow }">
              <el-radio
                v-if="store.duplicateAppids.includes(row.appid)"
                :model-value="localManagedGames[`game-${row.index}`] === true"
                :value="true"
                @change="() => onGameManagedChange(row)"
              >
                &nbsp;
              </el-radio>
            </template>
          </el-table-column>
          <el-table-column :label="STR.dataSourcePage.colVis" width="70">
            <template #default="{ row }: { row: GameRow }">
              <el-button
                v-if="store.gameVisibility[row.index] !== false"
                size="small"
                type="success"
                @click="store.setGameVisibility(row.index, false)"
              >
                ✅
              </el-button>
              <el-button
                v-else
                size="small"
                type="warning"
                @click="store.setGameVisibility(row.index, true)"
              >
                ❌
              </el-button>
            </template>
          </el-table-column>
          <el-table-column :label="STR.dataSourcePage.colAppid" width="90" prop="appid" />
          <el-table-column :label="STR.dataSourcePage.colName" min-width="140" prop="name" show-overflow-tooltip />
          <el-table-column :label="STR.dataSourcePage.colPath" min-width="200" class-name="horizontal-cell-scroll">
            <template #default="{ row }: { row: GameRow }">
              <div class="horizontal-cell-scroll">{{ ensureTrailingSlash(row.basepath) }}</div>
            </template>
          </el-table-column>
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
        </el-table>
      </el-card>

      <!-- MOD 表 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <span>{{ STR.dataSourcePage.modTable(store.filteredMods.length) }}</span>
        </template>
        <el-table :data="store.filteredMods" border stripe size="small">
          <el-table-column :label="STR.dataSourcePage.colIndex" width="60" type="index" />
          <el-table-column label="[选]" width="50">
            <template #default="{ row }: { row: ModRow }">
              <el-radio
                v-if="store.duplicateMixedIds.includes(`${row.appid}:${row.modid}`)"
                :model-value="localManagedMods[`mod-${row.index}`] === true"
                :value="true"
                @change="() => onModManagedChange(row)"
              >
                &nbsp;
              </el-radio>
            </template>
          </el-table-column>
          <el-table-column :label="STR.dataSourcePage.colModId" width="120" prop="modid" show-overflow-tooltip />
          <el-table-column :label="STR.dataSourcePage.colName" min-width="140" prop="name" show-overflow-tooltip />
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

    <!-- 底部按钮 -->
    <div v-if="store.lastResult" style="margin-bottom: 16px;">
      <el-button
        type="default"
        size="large"
        :loading="isSaving"
        :disabled="isSaving"
        @click="onSave"
      >
        {{ STR.dataSourcePage.saveCurrentSelection }}
      </el-button>
      <el-button
        type="primary"
        size="large"
        :loading="isSaving"
        :disabled="isSaving"
        @click="onConfirm"
      >
        {{ STR.dataSourcePage.confirmToRulesOverview }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useDataSourceStore } from '../stores/datasource'
import { useForestStore } from '../stores/forest'
import { apiPost } from '../api/client'
import { scrollintotabitem } from '../utils/scroll'
import { ensureTrailingSlash } from '../utils/paths'
import { STR } from '../locales/zh-CN'
import type { LibraryRow, GameRow, ModRow } from '../types'
import { showPopup } from '../utils/notify'
import { getDescription, extractCode } from '../utils/errorCodes'
import { ElMessage } from 'element-plus'

const store = useDataSourceStore()
const forestStore = useForestStore()
const router = useRouter()

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

  // Default output path
  const outputPath = store.databaseOutputPath || '/tmp/modmanager_database_generated.json'

  try {
    const resp = await apiPost('/database/save', {
      database: db,
      output_path: outputPath,
    })

    if (resp.ok) {
      // Pass database to forest store
      forestStore.storedDatabase = db
      forestStore.pipelineForm.manualSteamPath = store.manualPath
      forestStore.pipelineForm.databasePath = ''
      forestStore.dbManualOverride = false

      if (!forestStore.userConfig) {
        await forestStore.loadConfig()
      }
      if (forestStore.userConfig) {
        forestStore.pipelineForm.userConfigPath = '/tmp/modmanager_userconfig_generated.json'
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
async function onSave() {
  const ok = await doSave()
  if (ok) {
    ElMessage.success('已保存')
  }
}

// ── save & navigate to rules overview ──
async function onConfirm() {
  const ok = await doSave()
  if (ok) {
    router.push('/rules-overview')
  }
}

const isDiscoverDisabled = computed(() => {
  if (store.discoveryMode === 'manual') {
    return !store.manualPath
  }
  return false
})

onMounted(() => {
  store.loadFromCache()
})

onBeforeUnmount(() => {
  store.saveToCache()
})

async function onScan() {
  await store.scan()
}

function scrollToLibrary(libraryIndex: number) {
  // Find the library row's DOM element in the library table
  const rows = document.querySelectorAll('.el-table__body-wrapper tbody tr')
  // The library table is the first el-table on the page
  const tables = document.querySelectorAll('.el-table')
  if (tables.length > 0) {
    const libTableRows = tables[0].querySelectorAll('.el-table__body-wrapper tbody tr')
    const targetRow = libTableRows[libraryIndex]
    scrollintotabitem(targetRow as HTMLElement | null)
  }
}

function scrollToGame(gameIndex: number) {
  // The game table is the second el-table
  const tables = document.querySelectorAll('.el-table')
  if (tables.length > 1) {
    const gameTableRows = tables[1].querySelectorAll('.el-table__body-wrapper tbody tr')
    const targetRow = gameTableRows[gameIndex]
    scrollintotabitem(targetRow as HTMLElement | null)
  }
}

function scrollToFirstMod(game: GameRow) {
  // Find the first MOD for this game
  const firstMod = store.mods.find(
    m => m.appid === game.appid && m.gameIndex === game.index,
  )
  if (!firstMod) return

  // The MOD table is the third el-table
  const tables = document.querySelectorAll('.el-table')
  if (tables.length > 2) {
    const modTableRows = tables[2].querySelectorAll('.el-table__body-wrapper tbody tr')
    const targetRow = modTableRows[firstMod.index]
    scrollintotabitem(targetRow as HTMLElement | null)
  }
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
</style>
