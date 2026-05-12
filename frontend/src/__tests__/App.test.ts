import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

// Mock the API client
vi.mock('../api/client', () => ({
  apiPost: vi.fn(),
}))

import App from '../App.vue'
import { apiPost } from '../api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/datasource' },
    { path: '/datasource', name: 'datasource', component: { template: '<div>datasource</div>' } },
    { path: '/settings', name: 'settings', component: { template: '<div>settings</div>' } },
  ],
})

const mockedApiPost = vi.mocked(apiPost)

const elStubs = {
  'layout-shell': { template: '<div class="layout-shell-stub"><slot /></div>' },
}

describe('App.vue — startup navigation guard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('navigates to /settings when user_config_path is empty', async () => {
    mockedApiPost.mockResolvedValue({
      ok: true,
      data: {
        inputs: {
          user_config_path: '',
          database_path: '',
          rule_paths: [],
        },
        results: null,
      },
      errors: [],
      warnings: [],
    })

    // Push to '/' first
    await router.push('/')
    await router.isReady()

    const pushSpy = vi.spyOn(router, 'push')

    mount(App, {
      global: { plugins: [router], stubs: elStubs },
    })

    // Wait for onMounted to resolve
    await new Promise(process.nextTick)
    await new Promise(process.nextTick)

    expect(mockedApiPost).toHaveBeenCalledWith('/workspace/status', {})
    expect(pushSpy).toHaveBeenCalledWith('/settings')
  })

  it('does NOT navigate when user_config_path is configured', async () => {
    mockedApiPost.mockResolvedValue({
      ok: true,
      data: {
        inputs: {
          user_config_path: '/home/user/.config/kmm/user_config.json',
          database_path: '',
          rule_paths: [],
        },
        results: null,
      },
      errors: [],
      warnings: [],
    })

    await router.push('/')
    await router.isReady()

    const pushSpy = vi.spyOn(router, 'push')

    mount(App, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await new Promise(process.nextTick)

    expect(mockedApiPost).toHaveBeenCalledWith('/workspace/status', {})
    // push should not have been called with /settings
    expect(pushSpy).not.toHaveBeenCalledWith('/settings')
  })

  it('does NOT navigate when API call fails', async () => {
    mockedApiPost.mockRejectedValue(new Error('Network error'))

    await router.push('/')
    await router.isReady()

    const pushSpy = vi.spyOn(router, 'push')

    mount(App, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await new Promise(process.nextTick)

    expect(mockedApiPost).toHaveBeenCalledWith('/workspace/status', {})
    expect(pushSpy).not.toHaveBeenCalled()
  })
})
