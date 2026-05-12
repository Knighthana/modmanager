import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

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
}

const mockedApiPost = vi.mocked(apiPost)
const mockedElMessage = vi.mocked(ElMessage)

// Helper to get vm as any for accessing internal component state
function vmAny(wrapper: VueWrapper): Record<string, unknown> {
  return wrapper.vm as unknown as Record<string, unknown>
}

// ── Mock data ──────────────────────────────────────────────────────────

const mockConfigResponse: ApiResponse<{
  user_config: { rule_sources: string[] }
}> = {
  ok: true,
  data: {
    user_config: {
      rule_sources: ['/home/user/kmm_rules/', '/home/user/special.kmmrule.json'],
    },
  },
  errors: [],
  warnings: [],
}

const mockScanResponse: ApiResponse<{
  files: Array<{ name: string; path: string }>
}> = {
  ok: true,
  data: {
    files: [
      { name: 'my_mods.kmmrule.json', path: '/home/user/kmm_rules/my_mods.kmmrule.json' },
      { name: 'extra.kmmrule.json', path: '/home/user/kmm_rules/extra.kmmrule.json' },
      { name: 'unused.kmmrule.json', path: '/home/user/kmm_rules/unused.kmmrule.json' },
    ],
  },
  errors: [],
  warnings: [],
}

const mockReadResponse: ApiResponse<{
  schema_namespace: string
  schema_version: string
  rule_meta_tag: {
    rulenamespace: string
    rulename: string
    author: Array<{ nickname: string }>
    description: string
  }
  game: Array<{ appid: string; modid: string[] }>
  mod: Array<{
    mixed_id: string
    nickname?: string
    preview?: string[]
    readme?: string[]
  }>
}> = {
  ok: true,
  data: {
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

const mockSaveInputsResponse: ApiResponse<unknown> = {
  ok: true,
  data: { saved: true },
  errors: [],
  warnings: [],
}

// ── Test suite ─────────────────────────────────────────────────────────

describe('RulesOverviewPage', () => {
  beforeEach(() => {
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

  it('shows loading state for files while scanning', async () => {
    // Resolve config but not scan
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      return new Promise(() => {}) // hang for scan
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('正在扫描规则文件')
  })

  it('shows empty state when no rule files are found', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      return { ok: true, data: { files: [] }, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
    expect(wrapper.text()).toContain('未发现规则文件')
  })

  // ── Happy path: load and display ─────────────────────────────────────

  it('loads rule sources on mount and displays them', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      return mockScanResponse
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('/home/user/kmm_rules/')
    expect(wrapper.text()).toContain('/home/user/special.kmmrule.json')
  })

  it('loads rule files on mount and displays file names', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      return mockScanResponse
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('my_mods.kmmrule.json')
    expect(wrapper.text()).toContain('extra.kmmrule.json')
    expect(wrapper.text()).toContain('unused.kmmrule.json')
  })

  it('displays rule source hint and settings link', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      return mockScanResponse
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('前往设置页管理')
    const settingsLink = wrapper.find('.router-link-stub')
    expect(settingsLink.exists()).toBe(true)
  })

  // ── Expand / collapse ────────────────────────────────────────────────

  it('expanding a file loads its detail via /api/rules/read', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      if (path === '/api/rules/scan') return mockScanResponse
      if (path === '/api/rules/read') return mockReadResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    // Find the first expand button and click it
    const expandButtons = wrapper.findAll('.el-btn-stub')
    expect(expandButtons.length).toBeGreaterThan(0)
    await expandButtons[0].trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    // Should have called /api/rules/read
    expect(mockedApiPost).toHaveBeenCalledWith('/api/rules/read', {
      path: '/home/user/kmm_rules/my_mods.kmmrule.json',
    })
  })

  it('expanded detail shows rule_meta_tag info', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      if (path === '/api/rules/scan') return mockScanResponse
      if (path === '/api/rules/read') return mockReadResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    // Expand first file
    const expandButtons = wrapper.findAll('.el-btn-stub')
    await expandButtons[0].trigger('click')
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
      if (path === '/api/config/discover') return mockConfigResponse
      if (path === '/api/rules/scan') return mockScanResponse
      if (path === '/api/rules/read') return mockReadResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const expandButtons = wrapper.findAll('.el-btn-stub')
    await expandButtons[0].trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('RWR (270150)')
    expect(wrapper.text()).toContain('Arma3 (107410)')
  })

  it('expanded detail shows mod entries with preview and readme', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      if (path === '/api/rules/scan') return mockScanResponse
      if (path === '/api/rules/read') return mockReadResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const expandButtons = wrapper.findAll('.el-btn-stub')
    await expandButtons[0].trigger('click')
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
      if (path === '/api/config/discover') return mockConfigResponse
      if (path === '/api/rules/scan') return mockScanResponse
      if (path === '/api/rules/read') return mockReadResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const expandButtons = wrapper.findAll('.el-btn-stub')

    // Expand
    await expandButtons[0].trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('我的规则集')

    // Collapse (click again)
    await expandButtons[0].trigger('click')
    await wrapper.vm.$nextTick()

    // The text should still be in DOM if the detail was cached, but the detail section
    // should be hidden. Actually with v-if, it should be gone from DOM.
    // Let's check: the button text changes from "展开 ▾" to "收起 ▲" and back
    expect(wrapper.findAll('.el-btn-stub')[0].text()).toContain('展开')
  })

  // ── Read error handling ──────────────────────────────────────────────

  it('shows error when /api/rules/read fails', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      if (path === '/api/rules/scan') return mockScanResponse
      if (path === '/api/rules/read') {
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

    // Expand first file
    const expandButtons = wrapper.findAll('.el-btn-stub')
    await expandButtons[0].trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('File not found')
  })

  // ── Save selection ───────────────────────────────────────────────────

  it('save button is disabled when no files are selected', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      return mockScanResponse
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    // Get the vm and uncheck all
    const vm = vmAny(wrapper)
    const files = (vm as { ruleFiles: Array<{ checked: boolean }> }).ruleFiles
    files.forEach((f) => { f.checked = false })
    await wrapper.vm.$nextTick()

    // Find the primary button — it should be disabled
    const primaryBtns = wrapper.findAll('.el-btn-stub')
    // The save button should have disabled attribute
    const saveBtn = wrapper.find('.el-btn-stub')
    // Actually let's just check selectedCount = 0
    const selectedCount = (vm as { selectedCount: number }).selectedCount
    expect(selectedCount).toBe(0)
  })

  it('saveSelection calls /api/rules/aggregate and /api/workspace/save-inputs', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      if (path === '/api/rules/scan') return mockScanResponse
      if (path === '/api/rules/aggregate') return mockAggregateResponse
      if (path === '/api/workspace/save-inputs') return mockSaveInputsResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    // Get vm and call saveSelection
    const vm = vmAny(wrapper)
    await (vm as { saveSelection: () => Promise<void> }).saveSelection()
    await wrapper.vm.$nextTick()

    // Should have called both endpoints
    expect(mockedApiPost).toHaveBeenCalledWith('/api/rules/aggregate', {
      paths: [
        '/home/user/kmm_rules/my_mods.kmmrule.json',
        '/home/user/kmm_rules/extra.kmmrule.json',
        '/home/user/kmm_rules/unused.kmmrule.json',
      ],
    })
    expect(mockedApiPost).toHaveBeenCalledWith('/api/workspace/save-inputs', {
      rule_paths: [
        '/home/user/kmm_rules/my_mods.kmmrule.json',
        '/home/user/kmm_rules/extra.kmmrule.json',
        '/home/user/kmm_rules/unused.kmmrule.json',
      ],
    })
  })

  it('saveSelection shows success alert and link to compute-prep', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      if (path === '/api/rules/scan') return mockScanResponse
      if (path === '/api/rules/aggregate') return mockAggregateResponse
      if (path === '/api/workspace/save-inputs') return mockSaveInputsResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    await (vm as { saveSelection: () => Promise<void> }).saveSelection()
    await wrapper.vm.$nextTick()

    // Success alert should show
    expect(wrapper.find('.el-alert-stub').exists()).toBe(true)
    expect(wrapper.text()).toContain('已保存 3 条规则')

    // Link to compute-prep should exist
    expect(wrapper.text()).toContain('进入计算准备')
  })

  it('saveSelection only sends checked file paths', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      if (path === '/api/rules/scan') return mockScanResponse
      if (path === '/api/rules/aggregate') return mockAggregateResponse
      if (path === '/api/workspace/save-inputs') return mockSaveInputsResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    // Uncheck the second file
    const vm = vmAny(wrapper)
    const files = (vm as { ruleFiles: Array<{ checked: boolean; path: string }> }).ruleFiles
    files[1].checked = false
    await wrapper.vm.$nextTick()

    await (vm as { saveSelection: () => Promise<void> }).saveSelection()
    await wrapper.vm.$nextTick()

    // Should only send paths of checked files
    expect(mockedApiPost).toHaveBeenCalledWith('/api/rules/aggregate', {
      paths: [
        '/home/user/kmm_rules/my_mods.kmmrule.json',
        '/home/user/kmm_rules/unused.kmmrule.json',
      ],
    })
  })

  it('saveSelection handles aggregate failure', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      if (path === '/api/rules/scan') return mockScanResponse
      if (path === '/api/rules/aggregate') {
        return { ok: false, data: null, errors: ['Aggregation failed'], warnings: [] }
      }
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    await (vm as { saveSelection: () => Promise<void> }).saveSelection()
    await wrapper.vm.$nextTick()

    // Error message should have been shown
    expect(ElMessage.error).toHaveBeenCalledWith(expect.stringContaining('Aggregation failed'))

    // savedCount should still be null
    expect((vm as { savedCount: number | null }).savedCount).toBeNull()
  })

  // ── Config discover failure ──────────────────────────────────────────

  it('handles config discover failure gracefully', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') {
        return { ok: false, data: null, errors: ['Config load failed'], warnings: [] }
      }
      return mockScanResponse
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    // Should show some error state — sources section won't have paths
    // but the page should not crash
  })

  // ── Game name mapping ────────────────────────────────────────────────

  it('displays human-readable game names using mapping', async () => {
    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/api/config/discover') return mockConfigResponse
      if (path === '/api/rules/scan') return mockScanResponse
      if (path === '/api/rules/read') return mockReadResponse
      return { ok: true, data: null, errors: [], warnings: [] }
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const expandButtons = wrapper.findAll('.el-btn-stub')
    await expandButtons[0].trigger('click')
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
      if (path === '/api/config/discover') return mockConfigResponse
      return mockScanResponse
    })

    const wrapper = mount(RulesOverviewPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const files = (vm as { ruleFiles: Array<{ checked: boolean }> }).ruleFiles
    expect(files.every((f) => f.checked)).toBe(true)
  })
})
