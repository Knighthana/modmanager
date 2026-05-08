import { describe, it, expect, beforeEach, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import ForestPage from '../../pages/ForestPage.vue'
import { useForestStore } from '../../stores/forest'

// Stub router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/forest', name: 'forest', component: { template: '<div />' } },
  ],
})

// Mock apiPost
vi.mock('../../api/client', () => ({
  apiPost: vi.fn(),
}))

import { apiPost } from '../../api/client'

describe('ForestPage — onDbPathBlur (TODO-9)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  function createWrapper() {
    return shallowMount(ForestPage, {
      global: {
        plugins: [router],
      },
    })
  }

  it('does not call api when dbManualOverride is false (locked)', () => {
    createWrapper()
    const store = useForestStore()
    store.dbManualOverride = false
    store.pipelineForm.databasePath = '/some/path.json'
    expect(apiPost).not.toHaveBeenCalled()
  })

  it('does not call api when path is empty', () => {
    createWrapper()
    const store = useForestStore()
    store.dbManualOverride = true
    store.pipelineForm.databasePath = ''
    expect(apiPost).not.toHaveBeenCalled()
  })

  it('calls /database/load on blur with non-empty path', async () => {
    const mockApiPost = apiPost as ReturnType<typeof vi.fn>
    mockApiPost.mockResolvedValue({
      ok: true,
      data: { steamlib: [], game: [], mod: [] },
      errors: [],
      warnings: [],
    })

    const wrapper = createWrapper()
    const store = useForestStore()
    store.dbManualOverride = true
    store.pipelineForm.databasePath = '/some/path/database.json'

    // Access the onDbPathBlur method directly from the component instance
    await (wrapper.vm as unknown as { onDbPathBlur: () => Promise<void> }).onDbPathBlur()

    expect(mockApiPost).toHaveBeenCalledWith('/database/load', { path: '/some/path/database.json' })
  })

  it('sets dbManualOverride to false on successful load', async () => {
    const mockApiPost = apiPost as ReturnType<typeof vi.fn>
    mockApiPost.mockResolvedValue({
      ok: true,
      data: { steamlib: [], game: [], mod: [] },
      errors: [],
      warnings: [],
    })

    const wrapper = createWrapper()
    const store = useForestStore()
    store.dbManualOverride = true
    store.pipelineForm.databasePath = '/valid/path/database.json'

    await (wrapper.vm as unknown as { onDbPathBlur: () => Promise<void> }).onDbPathBlur()

    expect(store.dbManualOverride).toBe(false)
    expect(store.storedDatabase).toEqual({ steamlib: [], game: [], mod: [] })
  })

  it('keeps dbManualOverride true on failed load, preserving user input', async () => {
    const mockApiPost = apiPost as ReturnType<typeof vi.fn>
    mockApiPost.mockResolvedValue({
      ok: false,
      data: null,
      errors: ['file not found'],
      warnings: [],
    })

    const wrapper = createWrapper()
    const store = useForestStore()
    store.dbManualOverride = true
    store.pipelineForm.databasePath = '/invalid/path'

    await (wrapper.vm as unknown as { onDbPathBlur: () => Promise<void> }).onDbPathBlur()

    expect(store.dbManualOverride).toBe(true)
    expect(store.pipelineForm.databasePath).toBe('/invalid/path')
  })
})
