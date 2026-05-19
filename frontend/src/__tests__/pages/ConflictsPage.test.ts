import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
vi.mock('../../api/client', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}))

import ConflictsPage from '../../pages/ConflictsPage.vue'
import { useForestStore } from '../../stores/forest'
import { apiGet, apiPost } from '../../api/client'

const mockedApiGet = vi.mocked(apiGet)
const mockedApiPost = vi.mocked(apiPost)

// Stub router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/workspace/:workspaceId/conflicts', name: 'workspace-conflicts', component: { template: '<div />' } },
  ],
})

// Element Plus stubs
const elStubs = {
  'el-button': { template: '<button class="el-button-stub" :disabled="$attrs.disabled"><slot /></button>' },
  'el-tooltip': { template: '<span class="el-tooltip-stub"><slot /></span>' },
  'el-empty': { template: '<div class="el-empty-stub"><slot /><div v-if="$attrs.description">{{ $attrs.description }}</div></div>' },
  'el-table': { template: '<div class="el-table-stub"><slot /></div>' },
  'el-table-column': { template: '<div class="el-table-column-stub"><slot /></div>' },
  'el-radio-group': { template: '<div class="el-radio-group-stub"><slot /></div>' },
  'el-radio': { template: '<label class="el-radio-stub"><slot /></label>' },
}

describe('ConflictsPage', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    await router.push('/workspace/test-ws-1/conflicts')
  })

  it('renders empty state when conflictList is empty', () => {
    const wrapper = mount(ConflictsPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    // The empty state text comes from el-empty description attribute
    const emptyEl = wrapper.find('.el-empty-stub')
    expect(emptyEl.exists()).toBe(true)
    expect(emptyEl.text()).toContain('暂无冲突')
  })

  it('shows "重新计算" button disabled with tooltip when no lastSuccessfulParams', () => {
    const wrapper = mount(ConflictsPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useForestStore()
    expect(store.lastSuccessfulParams).toBeNull()

    // Find all stub buttons
    const buttons = wrapper.findAll('.el-button-stub')
    const recalcBtn = buttons.find(b => b.text().includes('重新计算'))
    expect(recalcBtn).toBeTruthy()
    // Button should be disabled
    expect(recalcBtn!.attributes('disabled')).toBeDefined()
    // Tooltip should be shown
    expect(wrapper.find('.el-tooltip-stub').exists()).toBe(true)
  })

  it('shows "重新计算" button enabled when lastSuccessfulParams exists', () => {
    const wrapper = mount(ConflictsPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useForestStore()
    store.lastSuccessfulParams = {
      database_name: 'default',
      aggregated_rule_set: { schema_namespace: 'KMM_RuleSet', operation: [] },
      dry_run: true,
    }

    // Re-mount to reflect store changes
    const wrapper2 = mount(ConflictsPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    // With params, the tooltip should not be shown
    expect(wrapper2.find('.el-tooltip-stub').exists()).toBe(false)
  })

  it('onRecalculate calls runPipeline with lastSuccessfulParams and current decisions', async () => {
    const wrapper = mount(ConflictsPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useForestStore()

    // Set up params and decisions
    store.lastSuccessfulParams = {
      database_name: 'default',
      aggregated_rule_set: { schema_namespace: 'KMM_RuleSet', operation: [{ mixed_id: '270150:1' }] },
      dry_run: true,
      action_orders: { replace: 1 },
    }
    store.setDecision('/a.png', '/m1/a.png')

    // Spy on runPipeline
    const runSpy = vi.spyOn(store, 'runPipeline').mockResolvedValue(undefined)

    // Call onRecalculate
    await (wrapper.vm as unknown as { onRecalculate: () => Promise<void> }).onRecalculate()

    expect(runSpy).toHaveBeenCalledWith({
      database_name: 'default',
      aggregated_rule_set: { schema_namespace: 'KMM_RuleSet', operation: [{ mixed_id: '270150:1' }] },
      managed_entries: undefined,
      branch_decisions: { '/a.png': '/m1/a.png' },
      dry_run: true,
      action_orders: { replace: 1 },
    })
  })

  it('onRecalculate does nothing when lastSuccessfulParams is null', async () => {
    const wrapper = mount(ConflictsPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useForestStore()
    expect(store.lastSuccessfulParams).toBeNull()

    const runSpy = vi.spyOn(store, 'runPipeline').mockResolvedValue(undefined)
    await (wrapper.vm as unknown as { onRecalculate: () => Promise<void> }).onRecalculate()

    expect(runSpy).not.toHaveBeenCalled()
  })

  it('clearDecisions button calls store.clearDecisions', async () => {
    const wrapper = mount(ConflictsPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useForestStore()
    const clearSpy = vi.spyOn(store, 'clearDecisions')

    const buttons = wrapper.findAll('.el-button-stub')
    const resetBtn = buttons.find(b => b.text().includes('重置决策'))
    expect(resetBtn).toBeTruthy()

    await resetBtn!.trigger('click')
    expect(clearSpy).toHaveBeenCalled()
  })

  it('confirm decision saves branch_decisions via workspace decisions API', async () => {
    mockedApiGet.mockResolvedValue({
      ok: true,
      data: { managed_entries: { game: {}, mod: {} } },
      errors: [],
      warnings: [],
    })
    mockedApiPost.mockResolvedValue({
      ok: true,
      data: { saved: true },
      errors: [],
      warnings: [],
    })

    const wrapper = mount(ConflictsPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useForestStore()

    // Set some decisions so the button is enabled
    store.setDecision('/a.png', '/m1/a.png')
    await wrapper.vm.$nextTick()

    const buttons = wrapper.findAll('.el-button-stub')
    const confirmBtn = buttons.find(b => b.text().includes('确认决策'))
    expect(confirmBtn).toBeTruthy()
    // Button should be enabled since there are decisions
    expect(confirmBtn!.attributes('disabled')).toBeUndefined()

    await confirmBtn!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(mockedApiGet).toHaveBeenCalledWith('/workspace/test-ws-1/decisions/load')
    expect(mockedApiPost).toHaveBeenCalledWith('/workspace/test-ws-1/decisions/save', {
      managed_entries: { game: {}, mod: {} },
      branch_decisions: { '/a.png': '/m1/a.png' },
    })
  })

  it('confirm decision button is disabled when no decisions made', () => {
    const wrapper = mount(ConflictsPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const buttons = wrapper.findAll('.el-button-stub')
    const confirmBtn = buttons.find(b => b.text().includes('确认决策'))
    expect(confirmBtn).toBeTruthy()
    // Button should be disabled since branchDecisions is empty
    expect(confirmBtn!.attributes('disabled')).toBeDefined()
  })
})
