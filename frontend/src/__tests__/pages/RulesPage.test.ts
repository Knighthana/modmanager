import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

// Mock the API client
vi.mock('../../api/client', () => ({
  apiPost: vi.fn(),
}))

import RulesPage from '../../pages/RulesPage.vue'
import { apiPost } from '../../api/client'
import type { ApiResponse } from '../../api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/rules', name: 'rules', component: { template: '<div />' } },
  ],
})

// Element Plus stubs
const elStubs = {
  'el-button': { template: '<button class="el-btn-stub" :disabled="$attrs.disabled"><slot /></button>' },
  'el-input': { template: '<input class="el-input-stub" />' },
  'el-form': { template: '<form class="el-form-stub"><slot /></form>' },
  'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-card': { template: '<div class="el-card-stub"><slot /></div>' },
  'el-table': { template: '<div class="el-table-stub"><slot /></div>' },
  'el-table-column': { template: '<div class="el-table-column-stub"><slot /></div>' },
  'el-empty': { template: '<div class="el-empty-stub">{{ $attrs.description }}</div>' },
  'el-dialog': { template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>' },
}

const mockedApiPost = vi.mocked(apiPost)

// Helper to get vm as any for accessing internal component state
function vmAny(wrapper: VueWrapper): Record<string, unknown> {
  return wrapper.vm as unknown as Record<string, unknown>
}

describe('RulesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the form with input and scan button', () => {
    const wrapper = mount(RulesPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    expect(wrapper.text()).toContain('规则文件管理')
    expect(wrapper.find('.el-input-stub').exists()).toBe(true)
    expect(wrapper.find('.el-btn-stub').exists()).toBe(true)
  })

  it('shows empty state before scanning', () => {
    const wrapper = mount(RulesPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const emptyEl = wrapper.find('.el-empty-stub')
    expect(emptyEl.exists()).toBe(true)
  })

  it('onScan calls /rules/scan API and updates ruleFiles ref', async () => {
    const apiResp: ApiResponse<{ files: Array<{ name: string; path: string; size: number }> }> = {
      ok: true,
      data: {
        files: [
          { name: 'rule1.json', path: '/dir/rule1.json', size: 100 },
          { name: 'rule2.json', path: '/dir/rule2.json', size: 200 },
        ],
      },
      errors: [],
      warnings: [],
    }
    mockedApiPost.mockResolvedValue(apiResp)

    const wrapper = mount(RulesPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    // Set form.rulesDir via the vm
    const vm = vmAny(wrapper)
    const form = vm.form as { rulesDir: string }
    form.rulesDir = '/some/dir'
    await (vm as { onScan: () => Promise<void> }).onScan()
    await wrapper.vm.$nextTick()

    expect(mockedApiPost).toHaveBeenCalledWith('/rules/scan', { dir: '/some/dir' })

    // Verify internal ref was updated
    const ruleFiles = (vm as unknown as { ruleFiles: Array<{ name: string }> }).ruleFiles
    expect(ruleFiles.length).toBe(2)
    expect(ruleFiles[0].name).toBe('rule1.json')
    expect(ruleFiles[1].name).toBe('rule2.json')
  })

  it('onScan handles API error gracefully', async () => {
    const apiResp: ApiResponse<null> = {
      ok: false,
      data: null,
      errors: ['directory not found: /bad/dir'],
      warnings: [],
    }
    mockedApiPost.mockResolvedValue(apiResp)

    const wrapper = mount(RulesPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper)
    const form = vm.form as { rulesDir: string }
    form.rulesDir = '/bad/dir'
    await (vm as { onScan: () => Promise<void> }).onScan()
    await wrapper.vm.$nextTick()

    // Table should still be empty
    const emptyEl = wrapper.find('.el-empty-stub')
    expect(emptyEl.exists()).toBe(true)
  })

  it('showContent calls /rules/read API and displays content in dialog', async () => {
    // First, mock scan response
    const scanResp: ApiResponse<{ files: Array<{ name: string; path: string; size: number }> }> = {
      ok: true,
      data: {
        files: [{ name: 'test.json', path: '/dir/test.json', size: 50 }],
      },
      errors: [],
      warnings: [],
    }
    mockedApiPost.mockResolvedValueOnce(scanResp)

    const wrapper = mount(RulesPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    // First scan
    const vm = vmAny(wrapper)
    const form = vm.form as { rulesDir: string }
    form.rulesDir = '/dir'
    await (vm as { onScan: () => Promise<void> }).onScan()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    // Now mock the read call
    const readResp: ApiResponse<{ content: string; name: string; path: string; size: number }> = {
      ok: true,
      data: {
        content: '{"key": "value"}',
        name: 'test.json',
        path: '/dir/test.json',
        size: 50,
      },
      errors: [],
      warnings: [],
    }
    mockedApiPost.mockResolvedValueOnce(readResp)

    // Call showContent with the row
    await (vm as unknown as {
      showContent: (row: { name: string; path: string }) => Promise<void>
    }).showContent({ name: 'test.json', path: '/dir/test.json' })

    // Should have called the read API
    expect(mockedApiPost).toHaveBeenCalledWith('/rules/read', { path: '/dir/test.json' })
  })
})
