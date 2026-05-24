import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

vi.mock('../../api/client', () => ({
  apiPost: vi.fn(),
  apiGet: vi.fn(),
}))

vi.mock('../../stores/app', () => ({
  useAppStore: vi.fn(() => ({
    currentWorkspaceId: 'test-ws-1',
  })),
}))

vi.mock('../../components/WorkspaceSelector.vue', () => ({
  default: {
    name: 'WorkspaceSelector',
    template: '<div data-test="workspace-selector" class="workspace-selector-stub"></div>',
    setup() {
      return { selectedWorkspaceId: '' }
    },
  },
}))

import AdvancedPage from '../../pages/AdvancedPage.vue'
import { apiPost, apiGet } from '../../api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/advanced', name: 'advanced', component: { template: '<div />' } },
  ],
})

const stubs = {
  'el-card': { template: '<div class="el-card-stub"><slot /></div>' },
  'el-tabs': { template: '<div class="el-tabs-stub"><slot /></div>' },
  'el-tab-pane': { template: '<div class="el-tab-pane-stub"><slot /></div>' },
  'el-input': { template: '<textarea class="el-input-stub"></textarea>' },
  'el-button': { template: '<button class="el-btn-stub"><slot /></button>' },
  'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
  DatabaseSelector: {
    template: '<div data-test="db-selector"></div>',
    setup() {
      return { selectedDatabase: 'default' }
    },
  },
}

const mockedApiPost = vi.mocked(apiPost)
const mockedApiGet = vi.mocked(apiGet)

function vmAny(wrapper: VueWrapper): Record<string, unknown> {
  return wrapper.vm as unknown as Record<string, unknown>
}

describe('AdvancedPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
    sessionStorage.setItem('modmanager:configIndex', JSON.stringify({ type: 'path', string: '/test/config.json' }))

    mockedApiPost.mockImplementation(async (path: string) => {
      if (path === '/database/read') {
        return { ok: true, data: { game: [], mod: [] }, errors: [], warnings: [] }
      }
      if (path === '/config/discover') {
        return {
          ok: true,
          data: {
            config: {
              databases: { default: { path: '/tmp/database.json' } },
            },
            config_index: '/tmp/user_config.json',
          },
          errors: [],
          warnings: [],
        }
      }
      return { ok: true, data: {}, errors: [], warnings: [] }
    })

    mockedApiGet.mockImplementation(async (path: string) => {
      if (path === '/workspace/test-ws-1/rules/aggregated') {
        return { ok: true, data: { schema_namespace: 'KMM_RuleSet', operation: [] }, errors: [], warnings: [] }
      }
      return { ok: true, data: {}, errors: [], warnings: [] }
    })
  })

  it('loads database tab on mount', async () => {
    mount(AdvancedPage, {
      global: { plugins: [router], stubs },
    })

    await new Promise(process.nextTick)
    expect(mockedApiPost).toHaveBeenCalledWith('/database/read', { database_name: 'default' })
  })

  it('auto refreshes aggregated tab when switched', async () => {
    const wrapper = mount(AdvancedPage, {
      global: { plugins: [router], stubs },
    })

    await new Promise(process.nextTick)
    const vm = vmAny(wrapper)
    // Set up workspace selector stub
    ;(wrapper.vm as any).workspaceSelectorRef = { selectedWorkspaceId: 'test-ws-1' }
    vm.activeTab = 'aggregated'
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    const calls = mockedApiGet.mock.calls.map((c) => c[0])
    expect(calls).toContain('/workspace/test-ws-1/rules/aggregated')
  })

  it('auto refreshes user config tab when switched', async () => {
    const wrapper = mount(AdvancedPage, {
      global: { plugins: [router], stubs },
    })

    await new Promise(process.nextTick)
    const vm = vmAny(wrapper)
    vm.activeTab = 'userConfig'
    await wrapper.vm.$nextTick()
    await new Promise(process.nextTick)

    const calls = mockedApiPost.mock.calls.map((c) => c[0])
    expect(calls.filter((c) => c === '/config/discover').length).toBeGreaterThan(0)
  })
})
