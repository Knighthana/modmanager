import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

// Mock the API client
vi.mock('../../api/client', () => ({
  apiPost: vi.fn(),
}))

vi.mock('../../utils/persistence', () => ({
  loadPersistent: () => null,
  savePersistent: () => {},
  clearPersistent: () => {},
  loadSidebarCollapsed: () => false,
  saveSidebarCollapsed: () => {},
  loadActiveTab: () => '',
  saveActiveTab: () => {},
  loadCurrentWorkspaceId: () => null,
  saveCurrentWorkspaceId: () => {},
  loadUiState: () => null,
  saveUiState: () => {},
  clearUiState: () => {},
  migrateOldWorkspace: () => {},
}))

import SettingsPage from '../../pages/SettingsPage.vue'
import { apiPost } from '../../api/client'
import type { ApiResponse } from '../../api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/settings', name: 'settings', component: { template: '<div />' } },
  ],
})

// Element Plus stubs (no TypeScript in templates!)
const elStubs = {
  'el-card': { template: '<div class="el-card-stub"><slot /></div>' },
  'el-form': { template: '<div class="el-form-stub"><slot /></div>' },
  'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-input': { template: '<input class="el-input-stub" />' },
  'el-button': { template: '<button class="el-btn-stub" :disabled="$attrs.disabled"><slot /></button>' },
  'el-divider': { template: '<div class="el-divider-stub"><slot /></div>' },
  'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
  'el-popconfirm': { template: '<div class="el-popconfirm-stub"><slot name="reference" /></div>' },
  'el-table': { template: '<div class="el-table-stub"><slot /><slot name="append" /></div>' },
  'el-table-column': { template: '<div class="el-table-column-stub"><slot :row="{}" :index="0" /></div>', props: ['prop', 'label', 'width'] },
  'el-dialog': { template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>' },
}

const mockedApiPost = vi.mocked(apiPost)

// Helper to get vm as any for accessing internal component state
function vmAny(wrapper: VueWrapper): Record<string, unknown> {
  return wrapper.vm as unknown as Record<string, unknown>
}

// Mock config data matching the new nested API response
const mockConfigData = {
  config: {
    baksuffix: 'mybackup',
    bakignore: ['*.log', 'node_modules/'],
    databases: {
      'default': { path: '/custom/path/database.json' },
    },
    rule_sources: {
      default: { paths: ['/home/user/rules/', '/home/user/custom.kmmrule.json'] },
    },
    first_use: false,
  },
  config_index: '/home/user/.config/kmm/user_config.json',
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.setItem('modmanager:configIndex', '/test/config.json')
  })

  it('renders the page title', () => {
    const wrapper = mount(SettingsPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    expect(wrapper.text()).toContain('设置')
  })

  it('loads config on mount and populates form fields', async () => {
    const apiResp: ApiResponse<typeof mockConfigData> = {
      ok: true,
      data: mockConfigData,
      errors: [],
      warnings: [],
    }
    mockedApiPost.mockResolvedValue(apiResp)

    const wrapper = mount(SettingsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    // Wait for onMounted to complete
    await new Promise(process.nextTick)
    await new Promise(process.nextTick)

    const vm = vmAny(wrapper)
    const form = vm.form as Record<string, unknown>

    expect(form.baksuffix).toBe('mybackup')
    expect(form.bakignore).toEqual(['*.log', 'node_modules/'])
    // Verify databases loaded correctly
    expect((form.databases as any)[0]?.key).toBe('default')
    // Verify rule_sources loaded as name→paths object
    const ruleSourcesMap = vm.ruleSourcesMap as Record<string, { paths: string[] }>
    expect(ruleSourcesMap).toEqual({
      default: { paths: ['/home/user/rules/', '/home/user/custom.kmmrule.json'] },
    })
    // Verify apiPost was called with the discover endpoint
    expect(mockedApiPost).toHaveBeenCalledWith('/config/discover', { config_index: '/test/config.json' })
  })

  it('onSaveConfig calls /api/config/save with correct data', async () => {
    const apiResp: ApiResponse<{ saved: boolean; timestamp: string }> = {
      ok: true,
      data: { saved: true, timestamp: '2026-05-13T10:00:00Z' },
      errors: [],
      warnings: [],
    }
    mockedApiPost.mockResolvedValue(apiResp)

    const wrapper = mount(SettingsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper)
    const form = vm.form as Record<string, unknown>
    // Pre-populate form
    form.baksuffix = 'testsuffix'

    form.bakignore = ['*.tmp']
    form.databases = [{ key: 'default', value: '/test/db.json' }]
    // Set rule_sources as object
    ;(vm as any).ruleSourcesMap = { default: { paths: ['/test/rules/'] } }

    // Call save
    await (vm.onSaveConfig as () => Promise<void>)()

    // onMounted calls /api/config/discover first, then onSaveConfig calls save
    expect(mockedApiPost).toHaveBeenLastCalledWith('/config/save', {
      config_index: '/test/config.json',
      config: {
        baksuffix: 'testsuffix',
        bakignore: ['*.tmp'],
        databases: { 'default': { path: '/test/db.json' } },
        rule_sources: { default: { paths: ['/test/rules/'] } },
      },
    })
  })

  it('confirmAddBakignore adds an item to bakignore list', async () => {
    mockedApiPost.mockResolvedValue({ ok: true, data: null, errors: [], warnings: [] })

    const wrapper = mount(SettingsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper)
    const form = vm.form as Record<string, unknown>

    // Start with empty list
    form.bakignore = []

    // Set adding mode
    await (vm.onAddBakignore as () => void)()

    // Set the new value directly on vm and confirm
    vm.newBakignore = '*.custom'
    await (vm.confirmAddBakignore as () => void)()

    expect(form.bakignore).toContain('*.custom')
    expect((form.bakignore as string[]).length).toBe(1)
  })

  it('removeBakignore removes an item from bakignore list', async () => {
    mockedApiPost.mockResolvedValue({ ok: true, data: null, errors: [], warnings: [] })

    const wrapper = mount(SettingsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper)
    const form = vm.form as Record<string, unknown>

    form.bakignore = ['a', 'b', 'c']
    await (vm.removeBakignore as (idx: number) => void)(1)

    expect(form.bakignore).toEqual(['a', 'c'])
  })

  it('addRuleSourceEntry opens the dialog and confirmRuleSourceDialog adds a new entry', async () => {
    mockedApiPost.mockResolvedValue({ ok: true, data: null, errors: [], warnings: [] })

    const wrapper = mount(SettingsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper) as any
    // Start with empty map
    vm.ruleSourcesMap = {}

    // Open add dialog
    vm.addRuleSourceEntry()
    expect(vm.ruleSourceDialogVisible).toBe(true)
    expect(vm.ruleSourceDialogIsAdd).toBe(true)

    // Fill in dialog fields
    vm.ruleSourceDialogName = 'custom'
    vm.ruleSourceDialogPaths = '/path/to/rules/\n/path/to/file.kmmrule.json'

    // Confirm
    vm.confirmRuleSourceDialog()

    const map = vm.ruleSourcesMap as Record<string, { paths: string[] }>
    expect(map).toHaveProperty('custom')
    expect(map.custom.paths).toEqual(['/path/to/rules/', '/path/to/file.kmmrule.json'])
    expect(vm.ruleSourceDialogVisible).toBe(false)
  })

  it('editRuleSourceEntry opens dialog with existing data', async () => {
    mockedApiPost.mockResolvedValue({ ok: true, data: null, errors: [], warnings: [] })

    const wrapper = mount(SettingsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper) as any
    vm.ruleSourcesMap = {
      default: { paths: ['/home/rules/', '/home/extra.kmmrule.json'] },
    }

    // Trigger computed update
    await wrapper.vm.$nextTick()

    // Edit entry at index 0
    vm.editRuleSourceEntry(0)
    expect(vm.ruleSourceDialogVisible).toBe(true)
    expect(vm.ruleSourceDialogIsAdd).toBe(false)
    expect(vm.ruleSourceDialogName).toBe('default')
    expect(vm.ruleSourceDialogPaths).toBe('/home/rules/\n/home/extra.kmmrule.json')
  })

  it('removeRuleSourceEntry removes an entry from ruleSourcesMap', async () => {
    mockedApiPost.mockResolvedValue({ ok: true, data: null, errors: [], warnings: [] })

    const wrapper = mount(SettingsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper) as any
    vm.ruleSourcesMap = {
      a: { paths: ['/a/'] },
      b: { paths: ['/b/'] },
      c: { paths: ['/c/'] },
    }

    // Trigger computed update
    await wrapper.vm.$nextTick()

    // Remove entry at index 0 ('a')
    vm.removeRuleSourceEntry(0)

    expect(vm.ruleSourcesMap).toEqual({
      b: { paths: ['/b/'] },
      c: { paths: ['/c/'] },
    })
  })

  // syncWorkspaceDatabases test removed — workspace localStorage no longer used
})
