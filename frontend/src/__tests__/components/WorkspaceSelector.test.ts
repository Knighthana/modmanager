import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import WorkspaceSelector from '../../components/WorkspaceSelector.vue'

vi.mock('../../api/client', () => ({
  apiPost: vi.fn(),
  apiGet: vi.fn(),
}))

import { apiGet } from '../../api/client'

const stubs = {
  'el-select': {
    template: '<select class="el-select-stub" :placeholder="placeholder"><slot /></select>',
    props: ['modelValue', 'placeholder'],
  },
  'el-option': {
    template: '<option class="el-option-stub"><slot /></option>',
    props: ['label', 'value'],
  },
}

function flushAll(): Promise<void> {
  return new Promise(process.nextTick)
}

describe('WorkspaceSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads workspace list on mount', async () => {
    vi.mocked(apiGet).mockResolvedValue({
      ok: true,
      data: { workspaces: [] },
      errors: [],
      warnings: [],
    })

    mount(WorkspaceSelector, {
      global: { stubs },
    })

    await flushAll()
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith('/workspace/list')
  })

  it('renders workspace options from API response', async () => {
    const workspaces = [
      {
        workspace_id: 'abc123',
        name: '工作区-A',
        database_name: 'default',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
        app_version: '0.1.0',
      },
      {
        workspace_id: 'def456',
        name: '工作区-B',
        database_name: 'default',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
        app_version: '0.1.0',
      },
    ]

    vi.mocked(apiGet).mockResolvedValue({
      ok: true,
      data: { workspaces },
      errors: [],
      warnings: [],
    })

    const wrapper = mount(WorkspaceSelector, {
      global: { stubs },
    })

    await flushAll()

    expect(wrapper.vm.selectedWorkspaceId).toBe('abc123')
    expect(wrapper.findAll('.el-option-stub').length).toBe(2)
  })

  it('shows placeholder when API fails', async () => {
    vi.mocked(apiGet).mockResolvedValue({
      ok: false,
      data: null,
      errors: ['network error'],
      warnings: [],
    })

    const wrapper = mount(WorkspaceSelector, {
      global: { stubs },
    })

    await flushAll()

    expect(wrapper.find('.el-option-stub').exists()).toBe(false)
    expect(wrapper.find('.el-select-stub').attributes('placeholder')).toBe('无可用工作区')
  })

  it('shows placeholder when workspace list is empty', async () => {
    vi.mocked(apiGet).mockResolvedValue({
      ok: true,
      data: { workspaces: [] },
      errors: [],
      warnings: [],
    })

    const wrapper = mount(WorkspaceSelector, {
      global: { stubs },
    })

    await flushAll()

    expect(wrapper.find('.el-option-stub').exists()).toBe(false)
    expect(wrapper.find('.el-select-stub').attributes('placeholder')).toBe('无可用工作区')
  })

  it('exposes selectedWorkspaceId via defineExpose', async () => {
    const workspaces = [
      {
        workspace_id: 'abc123',
        name: '工作区-A',
        database_name: 'default',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
        app_version: '0.1.0',
      },
    ]

    vi.mocked(apiGet).mockResolvedValue({
      ok: true,
      data: { workspaces },
      errors: [],
      warnings: [],
    })

    const wrapper = mount(WorkspaceSelector, {
      global: { stubs },
    })

    await flushAll()

    expect(wrapper.vm.selectedWorkspaceId).toBe('abc123')
  })
})
