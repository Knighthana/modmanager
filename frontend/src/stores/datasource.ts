import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { streamSse } from '../api/sse'
import { createPersistence } from '../utils/persistence'
import type { SseProgress } from '../api/sse'
import type {
  DiscoverMode,
  LibraryRow,
  GameRow,
  ModRow,
  DataSourceState,
} from '../types'

const DS_KEY = 'datasource'
const pers = createPersistence()

export const useDataSourceStore = defineStore('datasource', () => {
  // ── state ──────────────────────────────────────────────────────────────
  const discoveryMode = ref<DiscoverMode>('all')
  const manualPath = ref('')
  const workingPathstyle = ref('linux')
  const greedyParsing = ref(false)
  const databaseOutputPath = ref('/tmp/modmanager_database_generated.json')

  const libraries = ref<LibraryRow[]>([])
  const games = ref<GameRow[]>([])
  const mods = ref<ModRow[]>([])
  const warnings = ref<string[]>([])
  const errors = ref<string[]>([])

  const libraryVisibility = ref<Record<number, boolean>>({})
  const gameVisibility = ref<Record<number, boolean>>({})
  const duplicateResolutions = ref<Record<string, number>>({})

  const isScanning = ref(false)
  const lastResult = ref<Record<string, unknown> | null>(null)

  // ── getters ────────────────────────────────────────────────────────────
  const filteredGames = computed(() =>
    games.value.filter(g => libraryVisibility.value[g.libraryIndex] !== false),
  )

  const filteredMods = computed(() =>
    mods.value.filter(
      m =>
        libraryVisibility.value[m.libraryIndex] !== false &&
        gameVisibility.value[m.gameIndex] !== false,
    ),
  )

  const duplicateAppids = computed(() => {
    const seen: Record<string, number> = {}
    for (const g of games.value) {
      seen[g.appid] = (seen[g.appid] || 0) + 1
    }
    return Object.entries(seen)
      .filter(([, count]) => count > 1)
      .map(([appid]) => appid)
  })

  const duplicateMixedIds = computed(() => {
    const seen: Record<string, number> = {}
    for (const m of mods.value) {
      const key = `${m.appid}:${m.modid}`
      seen[key] = (seen[key] || 0) + 1
    }
    return Object.entries(seen)
      .filter(([, count]) => count > 1)
      .map(([mixedId]) => mixedId)
  })

  // ── actions ───────────────────────────────────────────────────────────
  async function scan() {
    isScanning.value = true
    warnings.value = []
    errors.value = []

    // Determine mode and paths for the API call
    let apiMode: string
    let apiPaths: string[] | null

    if (discoveryMode.value === 'manual') {
      apiMode = 'manual'
      apiPaths = [manualPath.value]
    } else if (discoveryMode.value === 'all') {
      apiMode = 'auto'
      apiPaths = manualPath.value ? [manualPath.value] : null
    } else {
      // 'auto'
      apiMode = 'auto'
      apiPaths = null
    }

    const params = {
      mode: apiMode,
      paths: apiPaths,
      workingPathstyle: workingPathstyle.value,
      greedyParsing: greedyParsing.value,
      cachePath: apiMode === 'manual' ? null : databaseOutputPath.value,
    }

    await streamSse('/database/generate', params, {
      onProgress(_p: SseProgress) {
        // could expose progress if needed
      },
      onResult(data: unknown) {
        const result = data as {
          ok: boolean
          data: Record<string, unknown>
          errors?: string[]
          warnings?: string[]
        }
        if (result.ok && result.data) {
          const rawDb = result.data as Record<string, unknown>
          lastResult.value = rawDb
          _populateFromDatabase(rawDb)
        } else if (result.errors?.length) {
          warnings.value.push(...result.errors.map(e => `E_${e}`))
        }
        if (result.warnings?.length) {
          warnings.value.push(...result.warnings)
        }
        isScanning.value = false
      },
      onError(msg: string) {
        warnings.value.push(msg)
        isScanning.value = false
      },
    })
  }

  function loadFromCache() {
    const saved = pers.load<Partial<DataSourceState>>(DS_KEY)
    if (!saved) return

    if (saved.discoveryMode) discoveryMode.value = saved.discoveryMode
    if (saved.manualPath) manualPath.value = saved.manualPath
    if (saved.workingPathstyle) workingPathstyle.value = saved.workingPathstyle
    if (saved.greedyParsing !== undefined) greedyParsing.value = saved.greedyParsing
    if (saved.databaseOutputPath) databaseOutputPath.value = saved.databaseOutputPath
    if (saved.libraries) libraries.value = saved.libraries
    if (saved.games) games.value = saved.games
    if (saved.mods) mods.value = saved.mods
    if (saved.warnings) warnings.value = saved.warnings
    if (saved.errors) errors.value = saved.errors
    if (saved.libraryVisibility) libraryVisibility.value = saved.libraryVisibility
    if (saved.gameVisibility) gameVisibility.value = saved.gameVisibility
    if (saved.duplicateResolutions) duplicateResolutions.value = saved.duplicateResolutions
    if (saved.lastResult) lastResult.value = saved.lastResult
  }

  function saveToCache() {
    const state: DataSourceState = {
      discoveryMode: discoveryMode.value,
      manualPath: manualPath.value,
      workingPathstyle: workingPathstyle.value,
      greedyParsing: greedyParsing.value,
      databaseOutputPath: databaseOutputPath.value,
      libraries: libraries.value,
      games: games.value,
      mods: mods.value,
      warnings: warnings.value,
      errors: errors.value,
      libraryVisibility: libraryVisibility.value,
      gameVisibility: gameVisibility.value,
      duplicateResolutions: duplicateResolutions.value,
      isScanning: isScanning.value,
      lastResult: lastResult.value,
    }
    pers.save(DS_KEY, state)
  }

  function clearCache() {
    pers.clear(DS_KEY)
    _resetState()
  }

  function setLibraryVisibility(index: number, visible: boolean) {
    libraryVisibility.value = { ...libraryVisibility.value, [index]: visible }
  }

  function setGameVisibility(index: number, visible: boolean) {
    gameVisibility.value = { ...gameVisibility.value, [index]: visible }
  }

  function setDuplicateResolution(appid: string, libraryIndex: number) {
    duplicateResolutions.value = { ...duplicateResolutions.value, [appid]: libraryIndex }
  }

  // ── internal helpers ──────────────────────────────────────────────────

  function _populateFromDatabase(db: Record<string, unknown>) {
    const steamlib = (db.steamlib as Array<Record<string, unknown>>) || []
    const gameList = (db.game as Array<Record<string, unknown>>) || []
    const mod = (db.mod as Array<Record<string, unknown>>) || []

    // Build library index: path → index
    const libIndex: Record<string, number> = {}
    const libArr: LibraryRow[] = []
    for (let i = 0; i < steamlib.length; i++) {
      const p = String(steamlib[i].path || '')
      libIndex[p] = i
      libArr.push({
        index: i,
        path: p,
        gameCount: (steamlib[i].game as Array<unknown>)?.length || 0,
        modCount: 0, // filled after mod counting
      })
    }

    // Build game list with library index
    const gameArr: GameRow[] = []

    for (let i = 0; i < gameList.length; i++) {
      const g = gameList[i]
      const appid = String(g.appid || '')
      const modpath = String(g.modpath || '')
      const basepath = String(g.basepath || '')

      // Determine library index by basepath prefix matching
      let gi = 0
      const bp = String(g.basepath || '')
      for (let li = 0; li < steamlib.length; li++) {
        const libPath = String(steamlib[li].path || '')
        if (libPath && bp.startsWith(libPath)) {
          gi = li
          break
        }
      }

      const modsFound = (g.mods_found as Array<unknown>) || []
      gameArr.push({
        index: i,
        appid,
        name: String(g.name || ''),
        basepath,
        modpath,
        modCount: modsFound.length,
        libraryIndex: gi,
        managed: (g as Record<string, unknown>).managed as boolean ?? false,
      })
    }

    // Build mod list — match to game via path prefix (not appid alone)
    const modArr: ModRow[] = []
    for (let i = 0; i < mod.length; i++) {
      const d = mod[i]
      const mixedId = String(d.mixed_id || '')
      const parts = mixedId.split(':')
      const appid = parts[0] || ''
      const modid = parts[1] || ''
      const modPath = String(d.path || '')
      
      // Match mod to game by modpath prefix
      let gameIndex = 0
      for (let gi = 0; gi < gameArr.length; gi++) {
        const gModpath = String(gameArr[gi].modpath || '')
        if (gModpath && modPath.startsWith(gModpath)) {
          gameIndex = gi
          break
        }
      }
      const gameRow = gameArr[gameIndex]
      const libraryIndex = gameRow ? gameRow.libraryIndex : 0

      modArr.push({
        index: i,
        modid,
        name: modid,
        appid,
        path: modPath,
        libraryIndex,
        gameIndex,
        managed: (d as Record<string, unknown>).managed as boolean ?? false,
      })
    }

    // Count mods per library
    for (const m of modArr) {
      if (libArr[m.libraryIndex]) {
        libArr[m.libraryIndex].modCount++
      }
    }

    libraries.value = libArr
    games.value = gameArr
    mods.value = modArr
    warnings.value = [...warnings.value, ...((db.warnings as string[]) || [])]
    errors.value = [...errors.value, ...((db.errors as string[]) || [])]

    // Initialize visibility
    const newLibVis: Record<number, boolean> = {}
    for (const l of libArr) {
      newLibVis[l.index] = libraryVisibility.value[l.index] ?? true
    }
    libraryVisibility.value = newLibVis

    const newGameVis: Record<number, boolean> = {}
    for (const g of gameArr) {
      newGameVis[g.index] = gameVisibility.value[g.index] ?? true
    }
    gameVisibility.value = newGameVis
  }

  function _resetState() {
    discoveryMode.value = 'all'
    manualPath.value = ''
    workingPathstyle.value = 'linux'
    greedyParsing.value = false
    databaseOutputPath.value = '/tmp/modmanager_database_generated.json'
    libraries.value = []
    games.value = []
    mods.value = []
    warnings.value = []
    errors.value = []
    libraryVisibility.value = {}
    gameVisibility.value = {}
    duplicateResolutions.value = {}
    isScanning.value = false
    lastResult.value = null
  }

  return {
    // state
    discoveryMode,
    manualPath,
    workingPathstyle,
    greedyParsing,
    databaseOutputPath,
    libraries,
    games,
    mods,
    warnings,
    errors,
    libraryVisibility,
    gameVisibility,
    duplicateResolutions,
    isScanning,
    lastResult,
    // getters
    filteredGames,
    filteredMods,
    duplicateAppids,
    duplicateMixedIds,
    // actions
    scan,
    loadFromCache,
    saveToCache,
    clearCache,
    setLibraryVisibility,
    setGameVisibility,
    setDuplicateResolution,
  }
})
