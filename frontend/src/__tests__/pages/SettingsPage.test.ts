import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

// Mock the API client
vi.mock('../../api/client', () => ({
  apiPost: vi.fn(),
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
}

const mockedApiPost = vi.mocked(apiPost)

// Helper to get vm as any for accessing internal component state
function vmAny(wrapper: VueWrapper): Record<string, unknown> {
  return wrapper.vm as unknown as Record<string, unknown>
}

// Mock config data matching the API response
const mockConfigData = {
  bakprefix: 'mybackup_',
  bakignore: ['*.log', 'node_modules/'],
  databases: {
    'default': { path: '/custom/path/database.json' },
  },
  aggregated_ruleset_output_path: '/custom/path/aggregated.json',
  rule_sources: ['/home/user/rules/', '/home/user/custom.kmmrule.json'],
  source_path: '/home/user/.config/kmm/user_config.json',
  first_use: false,
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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

    expect(form.bakprefix).toBe('mybackup_')
    expect(form.bakignore).toEqual(['*.log', 'node_modules/'])
    // Verify databases loaded correctly
    expect((form.databases as any)[0]?.key).toBe('default')
    expect(form.aggregatedOutputPath).toBe('/custom/path/aggregated.json')
    expect(form.ruleSources).toEqual(['/home/user/rules/', '/home/user/custom.kmmrule.json'])
    // Verify apiPost was called with the discover endpoint
    expect(mockedApiPost).toHaveBeenCalledWith('/config/discover', {})
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
    form.bakprefix = 'testprefix_'
    form.bakignore = ['*.tmp']
    form.databases = [{ key: 'default', value: '/test/db.json' }]
    form.aggregatedOutputPath = '/test/agg.json'
    form.ruleSources = ['/test/rules/']

    // Call save
    await (vm.onSaveConfig as () => Promise<void>)()

    // onMounted calls /api/config/discover first, then onSaveConfig calls save
    expect(mockedApiPost).toHaveBeenLastCalledWith('/config/save', {
      config: {
        bakprefix: 'testprefix_',
        bakignore: ['*.tmp'],
        databases: { 'default': { path: '/test/db.json' } },
        aggregated_ruleset_output_path: '/test/agg.json',
        rule_sources: ['/test/rules/'],
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

  it('confirmAddRuleSource adds an item to ruleSources list', async () => {
    mockedApiPost.mockResolvedValue({ ok: true, data: null, errors: [], warnings: [] })

    const wrapper = mount(SettingsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper)
    const form = vm.form as Record<string, unknown>

    form.ruleSources = ['/existing/']
    vm.newRuleSource = '/new/rule/'
    await (vm.confirmAddRuleSource as () => void)()

    expect(form.ruleSources).toEqual(['/existing/', '/new/rule/'])
  })

  it('removeRuleSource removes an item from ruleSources list', async () => {
    mockedApiPost.mockResolvedValue({ ok: true, data: null, errors: [], warnings: [] })

    const wrapper = mount(SettingsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper)
    const form = vm.form as Record<string, unknown>

    form.ruleSources = ['/a/', '/b/', '/c/']
    await (vm.removeRuleSource as (idx: number) => void)(0)

    expect(form.ruleSources).toEqual(['/b/', '/c/'])
  })

  it('syncs workspace perDatabase when database keys are renamed or removed', async () => {
    const discoverResp: ApiResponse<Record<string, unknown>> = {
      ok: true,
      data: {
        bakprefix: 'kmmbackup_',
        bakignore: [],
        databases: {
          legacy: { path: '/db/legacy.json' },
          drop: { path: '/db/drop.json' },
        },
        aggregated_ruleset_output_path: null,
        rule_sources: [],
        source_path: '/tmp/user_config.json',
        first_use: false,
      },
      errors: [],
      warnings: [],
    }
    const saveResp: ApiResponse<Record<string, unknown>> = {
      ok: true,
      data: { saved: true },
      errors: [],
      warnings: [],
    }

    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/config/discover') return discoverResp
      if (path === '/config/save') return saveResp
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    localStorage.setItem('modmanager:workspace', JSON.stringify({
      lastDatabase: 'legacy',
      perDatabase: {
        legacy: { decisions: { branch_decisions: { '/a': '/x' } }, results: null },
        drop: { decisions: {}, results: null },
      },
      aggregatedRuleSet: null,
      aggregatedRuleHash: '',
      aggregatedRuleMeta: null,
    }))

    const wrapper = mount(SettingsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await new Promise(process.nextTick)

    const vm = vmAny(wrapper)
    ;(vm.form as Record<string, unknown>).databases = [
      { key: 'renamed', value: '/db/renamed.json' },
    ]
    ;(vm.databaseRenameMap as Record<string, string>).legacy = 'renamed'

    await (vm.onSaveConfig as () => Promise<void>)()

    const ws = JSON.parse(localStorage.getItem('modmanager:workspace') || '{}')
    expect(ws.lastDatabase).toBe('renamed')
    expect(ws.perDatabase.renamed).toBeTruthy()
    expect(ws.perDatabase.legacy).toBeUndefined()
    expect(ws.perDatabase.drop).toBeUndefined()
  })
})
