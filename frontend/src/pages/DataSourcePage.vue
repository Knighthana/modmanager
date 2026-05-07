<template>
  <div>
    <h2>📡 数据源</h2>

    <!-- Mode + Settings -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <span>数据源发现</span>
      </template>
      <el-form label-width="140px">
        <el-form-item label="发现模式">
          <el-radio-group v-model="store.discoveryMode">
            <el-radio value="all">🌐 全部（自动 + 手动）</el-radio>
            <el-radio value="auto">🔍 仅自动</el-radio>
            <el-radio value="manual">📁 仅手动</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="Working pathstyle">
          <el-select v-model="store.workingPathstyle" style="width: 200px;">
            <el-option label="auto" value="auto" />
            <el-option label="linux" value="linux" />
            <el-option label="windows" value="windows" />
          </el-select>
        </el-form-item>
        <el-form-item label="Greedy parsing">
          <el-switch v-model="store.greedyParsing" />
        </el-form-item>
        <el-form-item label="Cache path">
          <el-input v-model="store.cachePath" placeholder="/tmp/modmanager_database_generated.json" />
        </el-form-item>
        <el-form-item
          v-if="store.discoveryMode === 'manual' || store.discoveryMode === 'all'"
          label="手动路径"
        >
          <el-input
            v-model="store.manualPath"
            placeholder="/tmp/fixture/steamapps"
          />
          <div style="font-size:12px;color:#999;margin-top:4px;">
            💡 指向 steamapps/ 目录（含 appmanifest 和 workshop/content 的父目录）
          </div>
        </el-form-item>
        <el-form-item>
          <el-button
            type="warning"
            :loading="store.isScanning"
            :disabled="store.isScanning || isDiscoverDisabled"
            @click="onScan"
          >
            {{ store.isScanning ? '扫描中...' : '🔍 扫描 Steam 库' }}
          </el-button>
          <span v-if="isDiscoverDisabled" style="margin-left: 8px; font-size: 12px; color: #999;">
            请输入手动路径
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 扫描结果 -->
    <template v-if="store.libraries.length > 0">
      <!-- 库摘要表 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <span>📊 库摘要 ({{ store.libraries.length }})</span>
        </template>
        <el-table :data="store.libraries" border stripe size="small">
          <el-table-column label="序号" width="60" type="index" />
          <el-table-column label="👁" width="70">
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
          <el-table-column label="库名" width="100">
            <template #default="{ row }: { row: LibraryRow }">
              库#{{ row.index + 1 }}
            </template>
          </el-table-column>
          <el-table-column label="游戏" width="80" prop="gameCount" />
          <el-table-column label="MOD" width="80" prop="modCount" />
          <el-table-column label="路径" min-width="200" class-name="horizontal-cell-scroll">
            <template #default="{ row }: { row: LibraryRow }">
              <div class="horizontal-cell-scroll">{{ row.path }}</div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 游戏表 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <span>📋 游戏 ({{ store.filteredGames.length }})</span>
        </template>
        <el-table :data="store.filteredGames" border stripe size="small">
          <el-table-column label="序号" width="60" type="index" />
          <el-table-column label="[选]" width="70">
            <template #default="{ row }: { row: GameRow }">
              <el-radio
                v-if="store.duplicateAppids.includes(row.appid)"
                v-model="store.duplicateResolutions[row.appid]"
                :value="row.libraryIndex"
                @change="(val: number) => store.setDuplicateResolution(row.appid, val)"
              >
                &nbsp;
              </el-radio>
            </template>
          </el-table-column>
          <el-table-column label="👁" width="70">
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
          <el-table-column label="appid" width="90" prop="appid" />
          <el-table-column label="名称" min-width="140" prop="name" show-overflow-tooltip />
          <el-table-column label="路径" min-width="200" class-name="horizontal-cell-scroll">
            <template #default="{ row }: { row: GameRow }">
              <div class="horizontal-cell-scroll">{{ row.basepath }}</div>
            </template>
          </el-table-column>
          <el-table-column label="MOD 数" width="80">
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
          <el-table-column label="所属库" width="80">
            <template #default="{ row }: { row: GameRow }">
              <el-button
                link
                type="primary"
                @click="scrollToLibrary(row.libraryIndex)"
              >
                库#{{ row.libraryIndex + 1 }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- MOD 表 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header>
          <span>📦 MOD ({{ store.filteredMods.length }})</span>
        </template>
        <el-table :data="store.filteredMods" border stripe size="small">
          <el-table-column label="序号" width="60" type="index" />
          <el-table-column label="[选]" width="70">
            <template #default="{ row }: { row: ModRow }">
              <el-radio
                v-if="store.duplicateAppids.includes(row.appid)"
                v-model="store.duplicateResolutions[row.appid]"
                :value="row.libraryIndex"
                @change="(val: number) => store.setDuplicateResolution(row.appid, val)"
              >
                &nbsp;
              </el-radio>
            </template>
          </el-table-column>
          <el-table-column label="MODID" width="120" prop="modid" show-overflow-tooltip />
          <el-table-column label="名称" min-width="140" prop="name" show-overflow-tooltip />
          <el-table-column label="所属 APPID" width="100">
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
          <el-table-column label="所属库" width="80">
            <template #default="{ row }: { row: ModRow }">
              <el-button
                link
                type="primary"
                @click="scrollToLibrary(row.libraryIndex)"
              >
                库#{{ row.libraryIndex + 1 }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="路径" min-width="200" class-name="horizontal-cell-scroll">
            <template #default="{ row }: { row: ModRow }">
              <div class="horizontal-cell-scroll">{{ row.path }}</div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <!-- 警告区 -->
    <div v-if="store.warnings.length > 0" style="margin-bottom: 16px;">
      <el-alert
        title="扫描警告"
        type="warning"
        :closable="false"
        show-icon
      >
        <template #default>
          <ul style="margin: 4px 0; padding-left: 20px;">
            <li v-for="(w, i) in store.warnings" :key="'w-' + i">
              {{ w }}
              <span v-if="w.includes('W_DUPLICATE_APPID')" style="color: var(--el-color-danger);">
                — 请在游戏表中选择需要保留的库
              </span>
            </li>
          </ul>
        </template>
      </el-alert>
    </div>

    <!-- 底部按钮 -->
    <div v-if="store.lastResult" style="margin-bottom: 16px;">
      <el-button
        type="primary"
        size="large"
        @click="applyAndGoToForest"
      >
        🚀 应用此数据源 → 前往 Forest
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useDataSourceStore } from '../stores/datasource'
import { useForestStore } from '../stores/forest'
import { scrollintotabitem } from '../utils/scroll'
import type { LibraryRow, GameRow, ModRow } from '../types'

const store = useDataSourceStore()
const forestStore = useForestStore()
const router = useRouter()

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

function applyAndGoToForest() {
  if (store.lastResult) {
    forestStore.storedDatabase = store.lastResult
    forestStore.pipelineForm.manualSteamPath = store.manualPath
    forestStore.pipelineForm.databasePath = ''
  }
  router.push('/forest')
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
