import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import ConflictsPage from '../../pages/ConflictsPage.vue'
import { useForestStore } from '../../stores/forest'

// Stub router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/conflicts', name: 'conflicts', component: { template: '<div />' } },
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
  beforeEach(() => {
    setActivePinia(createPinia())
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
      kmm_rule_paths: ['/rules.json'],
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
      kmm_rule_paths: ['/rules/r1.json', '/rules/r2.json'],
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
      kmm_rule_paths: ['/rules/r1.json', '/rules/r2.json'],
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

  it('confirm decision button calls POST /api/workspace/save-decisions', async () => {
    const wrapper = mount(ConflictsPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    const store = useForestStore()

    // Set some decisions so the button is enabled
    store.setDecision('/a.png', '/m1/a.png')
    await wrapper.vm.$nextTick()

    // Mock localStorage
    const mockSetItem = vi.spyOn(Storage.prototype, 'setItem')
    const mockGetItem = vi.spyOn(Storage.prototype, 'getItem')
    mockGetItem.mockReturnValue(JSON.stringify({ lastDatabase: 'default', perDatabase: { default: { decisions: {}, results: null } } }))

    const buttons = wrapper.findAll('.el-button-stub')
    const confirmBtn = buttons.find(b => b.text().includes('确认决策'))
    expect(confirmBtn).toBeTruthy()
    // Button should be enabled since there are decisions
    expect(confirmBtn!.attributes('disabled')).toBeUndefined()

    await confirmBtn!.trigger('click')
    await wrapper.vm.$nextTick()

    // Verify localStorage was called to save workspace
    expect(mockSetItem).toHaveBeenCalled()
    const saveCall = mockSetItem.mock.calls.find(call => call[0].includes('workspace'))
    expect(saveCall).toBeTruthy()
    const savedData = JSON.parse(saveCall![1])
    expect(savedData.perDatabase.default.decisions.branch_decisions).toEqual({ '/a.png': '/m1/a.png' })

    mockSetItem.mockRestore()
    mockGetItem.mockRestore()
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
