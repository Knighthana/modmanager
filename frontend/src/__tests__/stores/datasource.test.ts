import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDataSourceStore } from '../../stores/datasource'

// Helper to build a minimal valid database result
function makeMinimalDatabase(): Record<string, unknown> {
  return {
    steamlib: [
      {
        path: '/lib1/steamapps',
        contains_libraryfolders_vdf: false,
        game: ['270150'],
      },
      {
        path: '/lib2/steamapps',
        contains_libraryfolders_vdf: false,
        game: ['107410'],
      },
    ],
    game: [
      {
        appid: '270150',
        name: 'RWR',
        basepath: '/lib1/steamapps/common/RWR',
        modpath: '/lib1/steamapps/workshop/content/270150',
        mods_found: ['mod1', 'mod2'],
      },
      {
        appid: '107410',
        name: 'Arma 3',
        basepath: '/lib2/steamapps/common/Arma 3',
        modpath: '/lib2/steamapps/workshop/content/107410',
        mods_found: ['mod3'],
      },
    ],
    mod: [
      { mixed_id: '270150:mod1', path: '/lib1/steamapps/workshop/content/270150/mod1', localdate: 0 },
      { mixed_id: '270150:mod2', path: '/lib1/steamapps/workshop/content/270150/mod2', localdate: 0 },
      { mixed_id: '107410:mod3', path: '/lib2/steamapps/workshop/content/107410/mod3', localdate: 0 },
    ],
    warnings: [],
  }
}

describe('useDataSourceStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    sessionStorage.setItem('modmanager:configIndex', JSON.stringify({ type: 'path', string: '/test/config.json' }))
    vi.restoreAllMocks()
  })

  it('initialises with empty state', () => {
    const store = useDataSourceStore()
    expect(store.libraries).toEqual([])
    expect(store.games).toEqual([])
    expect(store.mods).toEqual([])
    expect(store.warnings).toEqual([])
    expect(store.isScanning).toBe(false)
    expect(store.lastResult).toBeNull()
    expect(store.discoveryMode).toBe('all')
    expect(store.filteredGames).toEqual([])
    expect(store.filteredMods).toEqual([])
    expect(store.duplicateAppids).toEqual([])
  })

  it('scan calls API and populates state from database result', async () => {
    const mockFetch = vi.fn()
    vi.stubGlobal('fetch', mockFetch)

    const db = makeMinimalDatabase()
    const sseData = {
      ok: true,
      data: db,
      errors: [],
      warnings: [],
    }
    const sseChunks = [
      `event: result\ndata: ${JSON.stringify(sseData)}\n\n`,
    ]
    const encoder = new TextEncoder()
    mockFetch.mockResolvedValue({
      ok: true,
      body: {
        getReader() {
          let idx = 0
          return {
            read() {
              if (idx >= sseChunks.length) {
                return Promise.resolve({ done: true, value: undefined })
              }
              return Promise.resolve({ done: false, value: encoder.encode(sseChunks[idx++]) })
            },
          }
        },
      },
    })

    const store = useDataSourceStore()
    await store.scan()

    // Should have populated libraries, games, mods
    expect(store.libraries.length).toBe(2)
    expect(store.games.length).toBe(2)
    expect(store.mods.length).toBe(3)
    expect(store.lastResult).not.toBeNull()
    expect(store.isScanning).toBe(false)
  })

  it('filteredGames excludes games from hidden libraries', () => {
    const store = useDataSourceStore()
    // Manually set library and game data
    store.libraries = [
      { index: 0, path: '/lib1', gameCount: 1, modCount: 2 },
      { index: 1, path: '/lib2', gameCount: 1, modCount: 1 },
    ]
    store.games = [
      { index: 0, appid: '270150', name: 'RWR', basepath: '', modpath: '', modCount: 2, libraryIndex: 0, managed: false },
      { index: 1, appid: '107410', name: 'Arma 3', basepath: '', modpath: '', modCount: 1, libraryIndex: 1, managed: false },
    ]
    store.libraryVisibility = { 0: true, 1: true }
    store.gameVisibility = { 0: true, 1: true }

    expect(store.filteredGames.length).toBe(2)

    // Hide library 0
    store.setLibraryVisibility(0, false)
    expect(store.filteredGames.length).toBe(1)
    expect(store.filteredGames[0].appid).toBe('107410')

    // Show library 0 again
    store.setLibraryVisibility(0, true)
    expect(store.filteredGames.length).toBe(2)
  })

  it('filteredMods uses AND logic (library AND game visibility)', () => {
    const store = useDataSourceStore()
    store.libraries = [
      { index: 0, path: '/lib1', gameCount: 1, modCount: 2 },
      { index: 1, path: '/lib2', gameCount: 1, modCount: 1 },
    ]
    store.games = [
      { index: 0, appid: '270150', name: 'RWR', basepath: '', modpath: '', modCount: 2, libraryIndex: 0, managed: false },
      { index: 1, appid: '107410', name: 'Arma 3', basepath: '', modpath: '', modCount: 1, libraryIndex: 1, managed: false },
    ]
    store.mods = [
      { index: 0, modid: 'mod1', name: 'mod1', appid: '270150', path: '', libraryIndex: 0, gameIndex: 0, managed: false },
      { index: 1, modid: 'mod2', name: 'mod2', appid: '270150', path: '', libraryIndex: 0, gameIndex: 0, managed: false },
      { index: 2, modid: 'mod3', name: 'mod3', appid: '107410', path: '', libraryIndex: 1, gameIndex: 1, managed: false },
    ]
    store.libraryVisibility = { 0: true, 1: true }
    store.gameVisibility = { 0: true, 1: true }

    expect(store.filteredMods.length).toBe(3)

    // Hide library 0
    store.setLibraryVisibility(0, false)
    expect(store.filteredMods.length).toBe(1) // only mod3 remains
    expect(store.filteredMods[0].modid).toBe('mod3')

    // Show library 0, hide game 1
    store.setLibraryVisibility(0, true)
    store.setGameVisibility(1, false)
    expect(store.filteredMods.length).toBe(2) // mod1, mod2
  })

  it('duplicateAppids detects appids appearing in multiple libraries', () => {
    const store = useDataSourceStore()
    store.games = [
      { index: 0, appid: '270150', name: 'RWR', basepath: '', modpath: '', modCount: 2, libraryIndex: 0, managed: false },
      { index: 1, appid: '270150', name: 'RWR', basepath: '', modpath: '', modCount: 2, libraryIndex: 1, managed: false },
      { index: 2, appid: '107410', name: 'Arma 3', basepath: '', modpath: '', modCount: 1, libraryIndex: 1, managed: false },
    ]

    expect(store.duplicateAppids).toEqual(['270150'])
  })

  it('setLibraryVisibility toggles visibility', () => {
    const store = useDataSourceStore()
    store.libraries = [{ index: 0, path: '/lib1', gameCount: 0, modCount: 0 }]
    store.libraryVisibility = { 0: true }

    store.setLibraryVisibility(0, false)
    expect(store.libraryVisibility[0]).toBe(false)

    store.setLibraryVisibility(0, true)
    expect(store.libraryVisibility[0]).toBe(true)
  })

  it('setGameVisibility toggles visibility', () => {
    const store = useDataSourceStore()
    store.games = [{ index: 0, appid: '270150', name: 'RWR', basepath: '', modpath: '', modCount: 0, libraryIndex: 0, managed: false }]
    store.gameVisibility = { 0: true }

    store.setGameVisibility(0, false)
    expect(store.gameVisibility[0]).toBe(false)

    store.setGameVisibility(0, true)
    expect(store.gameVisibility[0]).toBe(true)
  })

  it('setDuplicateResolution stores by appid', () => {
    const store = useDataSourceStore()
    store.setDuplicateResolution('270150', 1)
    expect(store.duplicateResolutions['270150']).toBe(1)

    store.setDuplicateResolution('270150', 0)
    expect(store.duplicateResolutions['270150']).toBe(0)
  })

  it('duplicateMixedIds detects mixed_ids appearing in multiple libraries', () => {
    const store = useDataSourceStore()
    store.mods = [
      { index: 0, modid: 'mod1', name: 'mod1', appid: '270150', path: '', libraryIndex: 0, gameIndex: 0, managed: false },
      { index: 1, modid: 'mod1', name: 'mod1', appid: '270150', path: '', libraryIndex: 1, gameIndex: 0, managed: false },
      { index: 2, modid: 'mod2', name: 'mod2', appid: '270150', path: '', libraryIndex: 0, gameIndex: 0, managed: false },
      { index: 3, modid: 'mod3', name: 'mod3', appid: '107410', path: '', libraryIndex: 1, gameIndex: 1, managed: false },
    ]

    expect(store.duplicateMixedIds).toEqual(['270150:mod1'])
  })
})
