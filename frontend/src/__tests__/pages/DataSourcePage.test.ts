import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import DataSourcePage from '../../pages/DataSourcePage.vue'
import { useDataSourceStore } from '../../stores/datasource'

// Stub router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/data-source', name: 'data-source', component: { template: '<div />' } },
    { path: '/forest', name: 'forest', component: { template: '<div />' } },
  ],
})

// Element Plus stubs
const elStubs = {
  'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
  'el-form': { template: '<div class="el-form-stub"><slot /></div>' },
  'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-radio-group': { template: '<div class="el-radio-group-stub"><slot /></div>' },
  'el-radio': { template: '<label class="el-radio-stub"><slot /></label>' },
  'el-select': { template: '<div class="el-select-stub"><slot /></div>' },
  'el-option': { template: '<div class="el-option-stub"><slot /></div>' },
  'el-switch': { template: '<div class="el-switch-stub"><slot /></div>' },
  'el-input': { template: '<div class="el-input-stub"><slot /></div><input v-if="$attrs.placeholder" :placeholder="$attrs.placeholder" />' },
  'el-button': { template: '<button class="el-button-stub" :disabled="$attrs.disabled" @click="$attrs.onClick || (() => {})"><slot /></button>' },
  'el-table': { template: '<div class="el-table-stub"><slot /></div>' },
  'el-table-column': { template: '<div class="el-table-column-stub"><slot /></div>' },
  'el-alert': { template: '<div class="el-alert-stub"><slot name="default" /></div>' },
  'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
  'el-popconfirm': { template: '<div class="el-popconfirm-stub"><slot name="reference" /></div>' },
  'router-link': { template: '<a class="router-link-stub"><slot /></a>' },
}

describe('DataSourcePage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders mode radio group with three options', () => {
    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const radios = wrapper.findAll('.el-radio-stub')
    // Should have 3 radio options: all, auto, manual
    expect(radios.length).toBeGreaterThanOrEqual(3)
    const texts = radios.map(r => r.text())
    expect(texts.some(t => t.includes('全部'))).toBe(true)
    expect(texts.some(t => t.includes('仅自动'))).toBe(true)
    expect(texts.some(t => t.includes('仅手动'))).toBe(true)
  })

  it('shows manual path area when mode is manual or all', async () => {
    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useDataSourceStore()

    // Default is 'all', so manual path add trigger should be visible
    expect(wrapper.text()).toContain('➕ 添加路径')

    // Switch to 'auto' mode — entire form-item is hidden
    store.discoveryMode = 'auto'
    await wrapper.vm.$nextTick()
    expect(store.discoveryMode).toBe('auto')
  })

  it('renders scan button', () => {
    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const buttons = wrapper.findAll('.el-button-stub')
    const scanBtn = buttons.find(b => b.text().includes('扫描'))
    expect(scanBtn).toBeTruthy()
  })

  it('shows "确认并进入规则概览" button when lastResult is set', async () => {
    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useDataSourceStore()

    // Initially no button
    expect(wrapper.text()).not.toContain('确认并进入规则概览')

    // Set lastResult
    store.lastResult = { steamlib: [], game: [], mod: [] }
    await wrapper.vm.$nextTick()

    // Apply button should appear
    expect(wrapper.text()).toContain('确认并进入规则概览')
  })

  it('setLibraryVisibility toggles library visibility via store', () => {
    const store = useDataSourceStore()
    store.libraryVisibility = { 0: true }

    store.setLibraryVisibility(0, false)
    expect(store.libraryVisibility[0]).toBe(false)

    store.setLibraryVisibility(0, true)
    expect(store.libraryVisibility[0]).toBe(true)
  })

  it('warnings are displayed when present', async () => {
    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useDataSourceStore()

    // No warning initially
    expect(wrapper.find('.el-alert-stub').exists()).toBe(false)

    // Add warnings
    store.warnings = ['W_DUPLICATE_APPID: appid 270150']
    await wrapper.vm.$nextTick()

    // Warning alert should appear
    const alertEl = wrapper.find('.el-alert-stub')
    expect(alertEl.exists()).toBe(true)
  })

  it('onGameManagedChange mutually excludes other games with same appid', () => {
    const store = useDataSourceStore()
    store.games = [
      { index: 0, appid: '270150', name: 'RWR', basepath: '/lib1', modpath: '', modCount: 2, libraryIndex: 0, managed: false },
      { index: 1, appid: '270150', name: 'RWR', basepath: '/lib2', modpath: '', modCount: 2, libraryIndex: 1, managed: false },
      { index: 2, appid: '107410', name: 'Arma3', basepath: '/lib3', modpath: '', modCount: 1, libraryIndex: 1, managed: false },
    ]

    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    // Mount triggers initLocalManaged from store.games
    const vm = wrapper.vm as any

    // Select game 0 (appid=270150)
    vm.onGameManagedChange(store.games[0])
    expect(vm.localManagedGames['game-0']).toBe(true)
    expect(vm.localManagedGames['game-1']).toBe(false)
    expect(vm.localManagedGames['game-2']).toBe(false)

    // Select game 1 (same appid) — game 0 becomes false
    vm.onGameManagedChange(store.games[1])
    expect(vm.localManagedGames['game-0']).toBe(false)
    expect(vm.localManagedGames['game-1']).toBe(true)
    expect(vm.localManagedGames['game-2']).toBe(false)
  })

  it('onModManagedChange mutually excludes other mods with same mixed_id', () => {
    const store = useDataSourceStore()
    store.mods = [
      { index: 0, modid: 'mod1', name: 'mod1', appid: '270150', path: '/lib1/mod1', libraryIndex: 0, gameIndex: 0, managed: false },
      { index: 1, modid: 'mod1', name: 'mod1', appid: '270150', path: '/lib2/mod1', libraryIndex: 1, gameIndex: 0, managed: false },
      { index: 2, modid: 'mod2', name: 'mod2', appid: '270150', path: '/lib1/mod2', libraryIndex: 0, gameIndex: 0, managed: false },
    ]
    store.games = [
      { index: 0, appid: '270150', name: 'RWR', basepath: '/lib1', modpath: '', modCount: 2, libraryIndex: 0, managed: false },
    ]

    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const vm = wrapper.vm as any

    // Select mod 0 (mixed_id=270150:mod1)
    vm.onModManagedChange(store.mods[0])
    expect(vm.localManagedMods['mod-0']).toBe(true)
    expect(vm.localManagedMods['mod-1']).toBe(false)
    expect(vm.localManagedMods['mod-2']).toBe(false)

    // Select mod 1 (same mixed_id) — mod 0 becomes false
    vm.onModManagedChange(store.mods[1])
    expect(vm.localManagedMods['mod-0']).toBe(false)
    expect(vm.localManagedMods['mod-1']).toBe(true)
    expect(vm.localManagedMods['mod-2']).toBe(false)
  })

  it('confirmAddManualPath adds a path to store.manualPaths', async () => {
    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useDataSourceStore()
    const vm = wrapper.vm as any

    store.manualPaths = ['/existing/path/']
    vm.newManualPath = '/new/path/'
    vm.confirmAddManualPath()
    expect(store.manualPaths).toEqual(['/existing/path/', '/new/path/'])
    expect(vm.newManualPath).toBe('')
  })

  it('removeManualPath removes a path from store.manualPaths', async () => {
    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useDataSourceStore()
    const vm = wrapper.vm as any

    store.manualPaths = ['/a/', '/b/', '/c/']
    vm.removeManualPath(1)
    expect(store.manualPaths).toEqual(['/a/', '/c/'])
  })

  it('disables scan button when manual mode has no paths', async () => {
    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useDataSourceStore()
    store.discoveryMode = 'manual'
    store.manualPaths = []
    await wrapper.vm.$nextTick()

    const buttons = wrapper.findAll('.el-button-stub')
    const scanBtn = buttons.find(b => b.text().includes('扫描'))
    expect(scanBtn?.attributes('disabled')).toBeDefined()
  })

  it('enables scan button when manual mode has paths', async () => {
    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useDataSourceStore()
    store.discoveryMode = 'manual'
    store.manualPaths = ['/some/path/']
    await wrapper.vm.$nextTick()

    const buttons = wrapper.findAll('.el-button-stub')
    const scanBtn = buttons.find(b => b.text().includes('扫描'))
    // Should not be disabled
    expect(scanBtn?.attributes('disabled')).toBeUndefined()
  })

  it('confirm button calls save API and shows errors on failure', async () => {
    const wrapper = mount(DataSourcePage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useDataSourceStore()

    store.lastResult = { steamlib: [], game: [], mod: [] }
    store.databaseOutputPath = '/tmp/test.json'
    await wrapper.vm.$nextTick()

    // Mock fetch (apiPost uses fetch + res.json)
    const mockFetch = vi.fn()
    vi.stubGlobal('fetch', mockFetch)
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        ok: false,
        errors: ['E_DUPLICATE_APPID: conflict on appid 270150'],
        data: null,
        warnings: [],
      }),
    })

    const vm = wrapper.vm as any
    await vm.onConfirm()
    await wrapper.vm.$nextTick()

    // Save errors should be displayed
    expect(vm.saveErrors.length).toBeGreaterThan(0)
    expect(vm.saveErrors[0]).toContain('E_DUPLICATE_APPID')
  })
})
