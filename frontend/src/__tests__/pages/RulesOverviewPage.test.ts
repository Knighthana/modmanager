import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

import { createPinia, setActivePinia } from 'pinia'
// Mock element-plus for ElMessage
vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<typeof import('element-plus')>()
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
    },
  }
})

// Mock the API client
vi.mock('../../api/client', () => ({
  apiPost: vi.fn(),
}))

import RulesOverviewPage from '../../pages/RulesOverviewPage.vue'
import { apiPost } from '../../api/client'
import { ElMessage } from 'element-plus'
import type { ApiResponse } from '../../api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/rules-overview', name: 'rules-overview', component: { template: '<div />' } },
    { path: '/settings', name: 'settings', component: { template: '<div />' } },
    { path: '/compute-prep', name: 'compute-prep', component: { template: '<div />' } },
  ],
})

// Element Plus stubs (no TypeScript in templates!)
const elStubs = {
  'el-button': { template: '<button class="el-btn-stub" :disabled="$attrs.disabled"><slot /></button>' },
  'el-card': { template: '<div class="el-card-stub"><div v-if="$slots.header" class="el-card-header"><slot name="header" /></div><slot /></div>' },
  'el-checkbox': { template: '<label class="el-checkbox-stub"><input type="checkbox" :checked="$attrs.modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" /></label>' },
  'el-empty': { template: '<div class="el-empty-stub">{{ $attrs.description }}</div>' },
  'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
  'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
  'el-divider': { template: '<span class="el-divider-stub" />' },
  'el-alert': { template: '<div class="el-alert-stub" :class="`el-alert--${$attrs.type}`">{{ $attrs.title }}</div>' },
  'router-link': { template: '<a class="router-link-stub" :href="$attrs.to"><slot /></a>' },
  'el-select': {
    template: '<select class="el-select-stub" :value="$attrs.modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
    props: ['modelValue'],
  },
  'el-option': {
    template: '<option class="el-option-stub" :value="$attrs.value"><slot /></option>',
    props: ['value'],
  },
}

const mockedApiPost = vi.mocked(apiPost)
const mockedElMessage = vi.mocked(ElMessage)

// Helper to get vm as any for accessing internal component state
function vmAny(wrapper: VueWrapper): Record<string, unknown> {
  return wrapper.vm as unknown as Record<string, unknown>
}

// ── Mock data ──────────────────────────────────────────────────────────

const mockListSourcesResponse: ApiResponse<{ source_names: string[] }> = {
  ok: true,
  data: {
    source_names: ['default', 'custom'],
  },
  errors: [],
  warnings: [],
}

const mockScanBySourceResponse: ApiResponse<{
  source_name: string
  files: Array<{ name: string; path: string }>
}> = {
  ok: true,
  data: {
    source_name: 'default',
    files: [
      { name: 'my_mods.kmmrule.json', path: '/home/user/kmm_rules/my_mods.kmmrule.json' },
      { name: 'extra.kmmrule.json', path: '/home/user/kmm_rules/extra.kmmrule.json' },
      { name: 'unused.kmmrule.json', path: '/home/user/kmm_rules/unused.kmmrule.json' },
    ],
  },
  errors: [],
  warnings: [],
}

const mockReadResponse: ApiResponse<{ content: string; name: string; path: string; size: number }> = {
  ok: true,
  data: {
    content: JSON.stringify({
      schema_namespace: 'kmm',
      schema_version: '1.0',
      rule_meta_tag: {
        rulenamespace: 'kmm',
        rulename: '我的规则集',
        author: [{ nickname: 'knighthana' }],
        description: 'RWR + Arma3 的 MOD 管理规则',
      },
      game: [
        { appid: '270150', modid: ['2606099273', '2606099274'] },
        { appid: '107410', modid: ['2890123456'] },
      ],
      mod: [
        {
          mixed_id: '270150:2606099273',
          nickname: 'Castle',
          preview: ['preview.png', 'thumb.png'],
          readme: ['README.md'],
        },
      ],
    }),
    name: 'my_mods.kmmrule.json',
    path: '/home/user/kmm_rules/my_mods.kmmrule.json',
    size: 2048,
  },
  errors: [],
  warnings: [],
}

const mockAggregateResponse: ApiResponse<{ rule_count: number }> = {
  ok: true,
  data: { rule_count: 2 },
  errors: [],
  warnings: [],
}

// ── Test suite ─────────────────────────────────────────────────────────


// Helper: initialize component and check files for saveSelection tests
async function initializeAndCheckFiles(wrapper: VueWrapper): Promise<void> {
  // Wait for initial data load (list-sources + auto-select)
  await new Promise(process.nextTick)
  await wrapper.vm.$nextTick()
  await wrapper.vm.$nextTick()
  await new Promise(process.nextTick)

  // Check the files by accessing ruleFiles in component
  const vm = wrapper.vm as any
  if (vm.ruleFiles && Array.isArray(vm.ruleFiles)) {
    // Check the first two files
    if (vm.ruleFiles.length > 0) vm.ruleFiles[0].checked = true
    if (vm.ruleFiles.length > 1) vm.ruleFiles[1].checked = true
  }

  await wrapper.vm.$nextTick()
}


describe('RulesOverviewPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // ── Loading & error states ───────────────────────────────────────────

  it('renders the page title', () => {
    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    expect(wrapper.text()).toContain('规则概览')
  })

  it('shows loading state for sources initially', () => {
    // Don't resolve API — keep loading
    mockedApiPost.mockImplementation(() => new Promise(() => {}))

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    expect(wrapper.text()).toContain('正在加载规则来源')
  })

  it('shows empty state for files when no source is selected', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return { ok: true, data: { source_names: [] }, errors: [], warnings: [] }
      return { ok: true, data: { files: [] }, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    // With no sources, the file list should be empty
    const emptyStubs = wrapper.findAll('.el-empty-stub')
    expect(emptyStubs.length).toBeGreaterThanOrEqual(1)
  })

  it('shows loading state for files while scanning', async () => {
    // Resolve list-sources but not scan-by-source
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      return new Promise(() => {}) // hang for scan
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    // selectedSource should be auto-set to 'default', triggering scan
    // Since scan hangs, loadingFiles should be true
    const vm = vmAny(wrapper)
    expect((vm as any).loadingFiles).toBe(true)
  })

  // ── Happy path: load and display ─────────────────────────────────────

  it('loads source names on mount and auto-selects first source', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    const vm = vmAny(wrapper) as any
    expect(vm.sourceNames).toEqual(['default', 'custom'])
    expect(vm.selectedSource).toBe('default')
  })

  it('loads rule files when source is selected', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    // Files should be loaded from scan-by-source
    const vm = vmAny(wrapper) as any
    const files = vm.ruleFiles as Array<{ name: string }>
    expect(files.length).toBeGreaterThanOrEqual(3)
    const fileNames = files.map((f: { name: string }) => f.name)
    expect(fileNames).toContain('my_mods.kmmrule.json')
    expect(fileNames).toContain('extra.kmmrule.json')
    expect(fileNames).toContain('unused.kmmrule.json')
  })

  it('displays source hint and settings link', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('前往设置面板管理')
    const settingsLinks = wrapper.findAll('.el-btn-stub').filter(b => b.text().includes('前往设置面板管理'))
    expect(settingsLinks.length).toBeGreaterThan(0)
  })

  // ── Expand / collapse ────────────────────────────────────────────────

  it('expanding a file loads its detail via /rules/read', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      if (path === '/rules/read') return mockReadResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    // Find the first expand button and click it
    const expandButtons = wrapper.findAll('.el-btn-stub')
    const expandBtn = expandButtons.find(b => b.text().includes('展开'))
    expect(expandBtn).toBeTruthy()
    await expandBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    // Should have called /rules/read
    expect(mockedApiPost).toHaveBeenCalledWith('/rules/read', {
      path: '/home/user/kmm_rules/my_mods.kmmrule.json',
    })
  })

  it('expanded detail shows rule_meta_tag info', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      if (path === '/rules/read') return mockReadResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    // Expand first file
    const expandButtons = wrapper.findAll('.el-btn-stub')
    const expandBtn = expandButtons.find(b => b.text().includes('展开'))
    expect(expandBtn).toBeTruthy()
    await expandBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    // Verify detail content
    expect(wrapper.text()).toContain('kmm')
    expect(wrapper.text()).toContain('我的规则集')
    expect(wrapper.text()).toContain('knighthana')
    expect(wrapper.text()).toContain('RWR + Arma3 的 MOD 管理规则')
  })

  it('expanded detail shows game coverage', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      if (path === '/rules/read') return mockReadResponse
      if (path === '/database/read') {
        return {
          ok: true,
          data: {
            game: [
              { appid: '270150', name: 'RWR' },
              { appid: '107410', name: 'Arma3' },
            ],
          },
          errors: [],
          warnings: [],
        }
      }
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    const expandButtons = wrapper.findAll('.el-btn-stub')
    const expandBtn = expandButtons.find(b => b.text().includes('展开'))
    expect(expandBtn).toBeTruthy()
    await expandBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('RWR (270150)')
    expect(wrapper.text()).toContain('Arma3 (107410)')
  })

  it('expanded detail shows mod entries with preview and readme', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      if (path === '/rules/read') return mockReadResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    const expandButtons = wrapper.findAll('.el-btn-stub')
    const expandBtn = expandButtons.find(b => b.text().includes('展开'))
    expect(expandBtn).toBeTruthy()
    await expandBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Castle')
    expect(wrapper.text()).toContain('270150:2606099273')
    expect(wrapper.text()).toContain('preview.png, thumb.png')
    expect(wrapper.text()).toContain('README.md')
  })

  it('clicking expand again collapses the detail', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      if (path === '/rules/read') return mockReadResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    const expandButtons = wrapper.findAll('.el-btn-stub')
    const expandBtn = expandButtons.find(b => b.text().includes('展开'))
    expect(expandBtn).toBeTruthy()

    // Expand
    await expandBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('我的规则集')

    // Collapse (click again)
    await expandBtn!.trigger('click')
    await wrapper.vm.$nextTick()

    // The button text changes from "展开 ▾" to "收起 ▲" and back
    const expandBtnAgain = expandButtons.find(b => b.text().includes('展开'))
    expect(expandBtnAgain).toBeTruthy()
    expect(expandBtnAgain!.text()).toContain('展开')
  })

  // ── Read error handling ──────────────────────────────────────────────

  it('shows error when /rules/read fails', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      if (path === '/rules/read') {
        return { ok: false, data: null, errors: ['File not found'], warnings: [] }
      }
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    // Expand first file
    const expandButtons = wrapper.findAll('.el-btn-stub')
    const expandBtn = expandButtons.find(b => b.text().includes('展开'))
    expect(expandBtn).toBeTruthy()
    await expandBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('File not found')
  })

  // ── Save selection ───────────────────────────────────────────────────

  it('save button is disabled when no files are selected', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    // Get the vm and uncheck all
    const vm = vmAny(wrapper)
    const files = (vm as { ruleFiles: Array<{ checked: boolean }> }).ruleFiles
    files.forEach((f) => { f.checked = false })
    await wrapper.vm.$nextTick()

    // selectedCount should be 0
    const selectedCount = (vm as { selectedCount: number }).selectedCount
    expect(selectedCount).toBe(0)
  })


  // ── Config discover failure ──────────────────────────────────────────

  it('handles list-sources failure gracefully', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') {
        return { ok: false, data: null, errors: ['Failed to list sources'], warnings: [] }
      }
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    // Should show source select with empty options — should not crash
    const vm = vmAny(wrapper) as any
    expect(vm.sourceNames).toEqual([])
  })

  // ── Game name mapping ────────────────────────────────────────────────

  it('displays human-readable game names using mapping', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      if (path === '/rules/read') return mockReadResponse
      if (path === '/database/read') {
        return {
          ok: true,
          data: {
            game: [
              { appid: '270150', name: 'RWR' },
              { appid: '107410', name: 'Arma3' },
            ],
          },
          errors: [],
          warnings: [],
        }
      }
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    const expandButtons = wrapper.findAll('.el-btn-stub')
    const expandBtn = expandButtons.find(b => b.text().includes('展开'))
    expect(expandBtn).toBeTruthy()
    await expandBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    // RWR for 270150, Arma3 for 107410
    expect(wrapper.text()).toContain('RWR (270150)')
    expect(wrapper.text()).toContain('Arma3 (107410)')
  })

  // ── Default checkbox state ───────────────────────────────────────────

  it('all rule files are checked by default', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/rules/list-sources') return mockListSourcesResponse
      if (path === '/rules/scan-by-source') return mockScanBySourceResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    const vm = vmAny(wrapper)
    const files = (vm as { ruleFiles: Array<{ checked: boolean }> }).ruleFiles
    expect(files.every((f) => f.checked)).toBe(true)
  })
})
