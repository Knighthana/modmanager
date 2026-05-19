import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'

// Mock element-plus for ElMessage
vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<typeof import('element-plus')>()
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warning: vi.fn(),
    },
  }
})

// Mock the API client
vi.mock('../../api/client', () => ({
  apiPost: vi.fn(),
  apiGet: vi.fn(),
}))

import ComputePrepPage from '../../pages/ComputePrepPage.vue'
import { apiPost, apiGet } from '../../api/client'
import { ElMessage } from 'element-plus'
import type { ApiResponse } from '../../api/client'
import { useForestStore } from '../../stores/forest'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/workspace/:workspaceId/compute', name: 'workspace-compute', component: { template: '<div />' } },
    { path: '/workspace/:workspaceId/forest', name: 'workspace-forest', component: { template: '<div />' } },
    { path: '/workspace/:workspaceId/rules', name: 'workspace-rules', component: { template: '<div />' } },
    { path: '/compute-prep', name: 'compute-prep', redirect: '/' },
    { path: '/rules-overview', name: 'rules-overview', redirect: '/' },
    { path: '/forest', name: 'forest', redirect: '/' },
  ],
})

// Element Plus stubs (no TypeScript in templates!)
const elStubs = {
  'el-button': { template: '<button class="el-btn-stub" :disabled="$attrs.disabled || undefined"><slot /></button>' },
  'el-card': { template: '<div class="el-card-stub"><slot /></div>' },
  'el-checkbox': {
    template:
      '<label class="el-checkbox-stub"><input type="checkbox" :checked="$attrs.modelValue" :indeterminate="$attrs.indeterminate" @change="$emit(\'update:modelValue\', ($event.target as HTMLInputElement).checked)" /></label>',
    props: ['modelValue', 'indeterminate'],
  },
  'el-empty': { template: '<div class="el-empty-stub">{{ $attrs.description }}<slot /></div>' },
  'el-table': { template: '<div class="el-table-stub"><slot /></div>' },
  'el-table-column': { template: '<div class="el-table-column-stub" />' },
  'router-link': { template: '<a class="router-link-stub" :href="$attrs.to"><slot /></a>' },
  'DatabaseSelector': {
    template: '<div data-test="database-selector-stub"></div>',
    props: ['modelValue'],
    setup() {
      return { selectedDatabase: ref('default') }
    },
  },
}

const mockedApiPost = vi.mocked(apiPost)
const mockedApiGet = vi.mocked(apiGet)

// Helper to get vm as any for accessing internal component state
function vmAny(wrapper: VueWrapper): Record<string, unknown> {
  return wrapper.vm as unknown as Record<string, unknown>
}

/** Helper: Set aggregatedRuleSet in Pinia store BEFORE mount (so onMounted loadData() sees it) */
function setAggregatedRuleSetBeforeMount() {
  const forestStore = useForestStore()
  forestStore.aggregatedRuleSet = { schema_namespace: 'KMM_RuleSet', operation: [] }
}

// ── Mock data ──────────────────────────────────────────────────────────

/** Status response WITHOUT aggregated_rule_path — triggers empty state */
const statusNoRules: Record<string, unknown> = {
  ok: true,
  data: {
    workspace: '/tmp/fixture/workspace',
    initialized: true,
    inputs: {},
    results: { timestamp: null },
  },
}

/** Status response WITH aggregated_rule_path — triggers data loading */
const statusWithRules: Record<string, unknown> = {
  ok: true,
  data: {
    workspace: '/tmp/fixture/workspace',
    initialized: true,
    inputs: {
      aggregated_rule_path: '/tmp/fixture/aggregated_rule_set.json',
    },
    results: { timestamp: null },
  },
}

/** Status response WITH existing results — enables [查看结果] */
const statusWithResults: Record<string, unknown> = {
  ok: true,
  data: {
    workspace: '/tmp/fixture/workspace',
    initialized: true,
    inputs: {
      aggregated_rule_path: '/tmp/fixture/aggregated_rule_set.json',
    },
    results: { timestamp: '2026-05-13T12:00:00Z' },
  },
}

const mockAffectedEntries: ApiResponse<{
  libraries: Array<{ index: number; path: string; game_count: number; mod_count: number }>
  games: Array<{ appid: string; name: string; basepath: string; libraryIndex: number; has_duplicate: boolean }>
  mods: Array<{ mixed_id: string; nickname: string; path: string; libraryIndex: number; gameIndex: number; has_duplicate: boolean }>
}> = {
  ok: true,
  data: {
    libraries: [
      { index: 0, path: '/mnt/d/SteamLibrary/steamapps', game_count: 2, mod_count: 3 },
      { index: 1, path: '/mnt/e/SteamLibrary/steamapps', game_count: 1, mod_count: 1 },
    ],
    games: [
      { appid: '270150', name: 'RWR', basepath: '/mnt/d/.../RWR', libraryIndex: 0, has_duplicate: true },
      { appid: '270150', name: 'RWR', basepath: '/mnt/e/.../RWR', libraryIndex: 1, has_duplicate: true },
      { appid: '107410', name: 'Arma3', basepath: '/mnt/d/.../Arma3', libraryIndex: 0, has_duplicate: false },
    ],
    mods: [
      { mixed_id: '270150:2606099273', nickname: 'Castle', path: '/mnt/d/.../2606099273', libraryIndex: 0, gameIndex: 0, has_duplicate: true },
      { mixed_id: '270150:2606099274', nickname: 'Forest', path: '/mnt/d/.../2606099274', libraryIndex: 0, gameIndex: 0, has_duplicate: false },
      { mixed_id: '270150:2606099273', nickname: 'Castle', path: '/mnt/e/.../2606099273', libraryIndex: 1, gameIndex: 1, has_duplicate: true },
    ],
  },
  errors: [],
  warnings: [],
}

// ── Test suite ─────────────────────────────────────────────────────────

describe('ComputePrepPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    localStorage.clear()
    sessionStorage.clear()

    // Mock global fetch for GET /api/workspace/status
    vi.stubGlobal('fetch', vi.fn())
  })

  // ── Empty state ─────────────────────────────────────────────────────

  it('renders the page title', () => {
    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    expect(wrapper.text()).toContain('计算准备')
  })

  it('shows empty state when no aggregated_rule_path', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusNoRules), { status: 200 }))

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    // Wait for mount async
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
    expect(wrapper.text()).toContain('请先在规则概览选择规则')
    expect(wrapper.text()).toContain('前往规则概览')
  })

  it('shows empty state when status has no inputs', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify({
      ok: true,
      data: { workspace: '/tmp/ws', inputs: null, results: { timestamp: null } },
    }), { status: 200 }))

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    expect(wrapper.text()).toContain('请先在规则概览选择规则')
  })

  it('restores aggregated ruleset from backend when in-memory cache is missing', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))

    await router.push('/workspace/test-ws-1/compute')

    mockedApiGet.mockImplementation(async (path: string) => {
      if (path === '/workspace/test-ws-1/rules/aggregated') {
        return {
          ok: true,
          data: { schema_namespace: 'KMM_RuleSet', operation: [] },
          errors: [],
          warnings: [],
        }
      }
      return { ok: true, data: null, errors: [], warnings: [] }
    })
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/affected-entries') {
        return mockAffectedEntries
      }
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const apiGetPaths = mockedApiGet.mock.calls.map((c) => c[0])
    const apiPostPaths = mockedApiPost.mock.calls.map((c) => c[0])
    expect(apiGetPaths).toContain('/workspace/test-ws-1/rules/aggregated')
    expect(apiPostPaths).toContain('/rules/affected-entries')
    expect(wrapper.text()).not.toContain('请先在规则概览选择规则')
  })

  // ── Happy path: load and display ────────────────────────────────────

  it('loads affected entries and populates libraries, games, mods', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet in Pinia store BEFORE mount (so onMounted loadData() sees it)
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const state = vm as {
      libraries: Array<{ index: number; path: string; _checked: boolean; _visible: boolean }>
      games: Array<{ appid: string; _checked: boolean; has_duplicate: boolean }>
      mods: Array<{ mixed_id: string; _checked: boolean; has_duplicate: boolean }>
    }

    expect(state.libraries.length).toBe(2)
    expect(state.libraries[0].path).toBe('/mnt/d/SteamLibrary/steamapps')
    expect(state.libraries[1].path).toBe('/mnt/e/SteamLibrary/steamapps')

    expect(state.games.length).toBe(3)
    expect(state.mods.length).toBe(3)

    // Should have called /rules/affected-entries with aggregated_rule_set object (among other calls)
    const calls = mockedApiPost.mock.calls
    const affectedEntriesCall = calls.find(call => call[0] === '/rules/affected-entries')
    expect(affectedEntriesCall).toBeDefined()
    expect(affectedEntriesCall?.[1]).toEqual({
      aggregated_rule_set: { schema_namespace: 'KMM_RuleSet', operation: [] },
      database_name: 'default',
    })
  })

  it('all checkboxes default to checked', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const state = vm as {
      libraries: Array<{ _checked: boolean }>
      games: Array<{ _checked: boolean }>
      mods: Array<{ _checked: boolean }>
    }

    expect(state.libraries.every((l) => l._checked)).toBe(true)
    expect(state.games.every((g) => g._checked)).toBe(true)
    expect(state.mods.every((m) => m._checked)).toBe(true)
  })

  // ── Summary text ────────────────────────────────────────────────────

  it('computes summary text with duplicate counts', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    // Summary text: "覆盖 2 个库，2 个游戏 (1 个有多个入口)，2 个 MOD (1 个有多个入口)"
    // (2 unique game appids: 270150, 107410 → 1 has duplicate; 2 unique mod mixed_ids: one has duplicate)
    const wrapperText = wrapper.text()
    expect(wrapperText).toContain('覆盖')
    expect(wrapperText).toContain('2 个库')
    expect(wrapperText).toContain('2 个游戏')
    expect(wrapperText).toContain('1 个有多个入口')
    // Check mod counts: unique mixed_ids: '270150:2606099273', '270150:2606099274' → 2 unique, 1 has duplicate
    expect(wrapperText).toContain('2 个 MOD')
  })

  // ── Library tri-state checkbox ──────────────────────────────────────

  it('library toggleLibrary sets all children', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const comp = vm as {
      toggleLibrary: (libIndex: number, newVal: boolean) => void
      libraries: Array<{ index: number; _checked: boolean; _indeterminate: boolean }>
      games: Array<{ libraryIndex: number; _checked: boolean }>
      mods: Array<{ libraryIndex: number; _checked: boolean }>
    }

    // Toggle library 0 to false
    comp.toggleLibrary(0, false)

    // All games/mods in library 0 should be unchecked
    const lib0Games = comp.games.filter((g) => g.libraryIndex === 0)
    const lib0Mods = comp.mods.filter((m) => m.libraryIndex === 0)
    expect(lib0Games.every((g) => g._checked === false)).toBe(true)
    expect(lib0Mods.every((m) => m._checked === false)).toBe(true)

    // Library 0 should be not checked, not indeterminate
    expect(comp.libraries[0]._checked).toBe(false)
    expect(comp.libraries[0]._indeterminate).toBe(false)

    // Library 1 should be unaffected
    const lib1Games = comp.games.filter((g) => g.libraryIndex === 1)
    const lib1Mods = comp.mods.filter((m) => m.libraryIndex === 1)
    expect(lib1Games.every((g) => g._checked === true)).toBe(true)
    expect(lib1Mods.every((m) => m._checked === true)).toBe(true)
  })

  it('child change triggers recalcLibraryState to indeterminate', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const comp = vm as {
      onChildChange: (libIndex: number) => void
      libraries: Array<{ index: number; _checked: boolean; _indeterminate: boolean }>
      games: Array<{ libraryIndex: number; _checked: boolean; appid: string }>
    }

    // Uncheck one game in library 0
    const gameToUncheck = comp.games.find((g) => g.libraryIndex === 0)
    if (gameToUncheck) {
      gameToUncheck._checked = false
      comp.onChildChange(0)

      // Library 0 should now be indeterminate
      expect(comp.libraries[0]._checked).toBe(false)
      expect(comp.libraries[0]._indeterminate).toBe(true)
    }
  })

  it('child change all unchecked makes library unchecked (not indeterminate)', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const comp = vm as {
      toggleLibrary: (libIndex: number, newVal: boolean) => void
      onChildChange: (libIndex: number) => void
      libraries: Array<{ index: number; _checked: boolean; _indeterminate: boolean }>
      games: Array<{ libraryIndex: number; _checked: boolean }>
      mods: Array<{ libraryIndex: number; _checked: boolean }>
    }

    // Uncheck all children of library 0
    comp.games.filter((g) => g.libraryIndex === 0).forEach((g) => { g._checked = false })
    comp.mods.filter((m) => m.libraryIndex === 0).forEach((m) => { m._checked = false })
    comp.onChildChange(0)

    expect(comp.libraries[0]._checked).toBe(false)
    expect(comp.libraries[0]._indeterminate).toBe(false)
  })

  // ── Visibility toggle ───────────────────────────────────────────────

  it('toggleLibraryVisibility toggles _visible flag', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const comp = vm as {
      toggleLibraryVisibility: (libIndex: number) => void
      libraries: Array<{ index: number; _visible: boolean }>
    }

    // Library 0 is visible by default
    expect(comp.libraries[0]._visible).toBe(true)

    // Toggle visibility
    comp.toggleLibraryVisibility(0)
    expect(comp.libraries[0]._visible).toBe(false)

    // Toggle again
    comp.toggleLibraryVisibility(0)
    expect(comp.libraries[0]._visible).toBe(true)
  })

  // ── Duplicate row highlighting ──────────────────────────────────────

  it('gameRowClass returns duplicate-row for has_duplicate games', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const comp = vm as {
      gameRowClass: (data: { row: Record<string, unknown> }) => string
      modRowClass: (data: { row: Record<string, unknown> }) => string
    }

    expect(comp.gameRowClass({ row: { _checked: true, appid: '270150', has_duplicate: true } })).toBe('duplicate-row')
    expect(comp.gameRowClass({ row: { _checked: true, appid: '107410', has_duplicate: false } })).toBe('')
    expect(comp.modRowClass({ row: { _checked: true, mixed_id: '270150:2606099273', has_duplicate: true } })).toBe('duplicate-row')
    expect(comp.modRowClass({ row: { _checked: true, mixed_id: '107410:2890123456', has_duplicate: false } })).toBe('')
  })

  // ── Managed entries construction ─────────────────────────────────────

  it('buildManagedEntries returns empty when all checked', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const comp = vm as { buildManagedEntries: () => { game: Record<string, string[]>; mod: Record<string, string[]> } }

    const entries = comp.buildManagedEntries()
    expect(entries.game).toEqual({})
    expect(entries.mod).toEqual({})
  })

  it('buildManagedEntries includes appid when some unchecked', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const comp = vm as {
      buildManagedEntries: () => { game: Record<string, string[]>; mod: Record<string, string[]> }
      games: Array<{ appid: string; _checked: boolean; basepath: string }>
      mods: Array<{ mixed_id: string; _checked: boolean; path: string }>
    }

    // Uncheck one RWR entry
    const rwrEntry = comp.games.find((g) => g.appid === '270150' && g._checked === true)
    if (rwrEntry) {
      rwrEntry._checked = false
    }

    const entries = comp.buildManagedEntries()
    // 270150 should now be in managed entries because we unchecked one of its two entries
    expect(entries.game['270150']).toBeDefined()
    // The kept path should be only the one still checked
    expect(entries.game['270150'].length).toBe(1)
  })

  it('buildManagedEntries includes mods when some unchecked', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const comp = vm as {
      buildManagedEntries: () => { game: Record<string, string[]>; mod: Record<string, string[]> }
      mods: Array<{ mixed_id: string; _checked: boolean; path: string }>
    }

    // Uncheck one Castle entry
    const castleEntry = comp.mods.find((m) => m.mixed_id === '270150:2606099273' && m._checked === true)
    if (castleEntry) {
      castleEntry._checked = false
    }

    const entries = comp.buildManagedEntries()
    expect(entries.mod['270150:2606099273']).toBeDefined()
    expect(entries.mod['270150:2606099273'].length).toBe(1)
  })

  // ── Compute flow ────────────────────────────────────────────────────
  // NOTE: startCompute uses streamSse() which requires different mocking
  // These tests would need SSE stream mocking to work properly
  // Skipping for now as they're better tested in integration tests
  
  // ── View results ────────────────────────────────────────────────────

  it('viewResults navigates to /forest', async () => {
    const pushSpy = vi.spyOn(router, 'push')
    await router.push('/workspace/test-ws-1/compute')

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper)
    const comp = vm as { viewResults: () => void }
    comp.viewResults()

    expect(pushSpy).toHaveBeenLastCalledWith('/workspace/test-ws-1/forest')
  })

  it('canViewResults is true when forest store has existing results', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    // affected-entries still needed
    mockedApiPost.mockResolvedValue(mockAffectedEntries)

    // Set aggregatedRuleSet and existing results in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()
    const forestStore = useForestStore()
    forestStore.trees = [{ root_path: '/a', resolved_state: 'pending', destin_mixed_id: '', changerequest: [], refs: [], candidates: [] }]
    forestStore.finalMapping = [{ path: '/a', mixed_id: 'test:1', hashtype: 'sha256', hashvalue: 'abc' }]

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const comp = vm as { canViewResults: boolean }
    expect(comp.canViewResults).toBe(true)
  })

  // ── handle fetch errors ─────────────────────────────────────────────

  it('shows loadingFailed when affected-entries API fails', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue(new Response(JSON.stringify(statusWithRules), { status: 200 }))
    mockedApiPost.mockResolvedValue({
      ok: false,
      data: null,
      errors: ['Failed to load entries'],
      warnings: [],
    })

    // Set aggregatedRuleSet in Pinia store BEFORE mount
    setAggregatedRuleSetBeforeMount()

    const wrapper = mount(ComputePrepPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const comp = vm as { loadingFailed: boolean; loadingErrorMessage: string }
    expect(comp.loadingFailed).toBe(true)
    // The error message comes from the mock's errors array
    expect(comp.loadingErrorMessage).toContain('Failed to load entries')
  })
})
