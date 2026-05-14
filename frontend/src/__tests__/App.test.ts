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

  it('renders the shell component', () => {
    const wrapper = mount(App, {
      global: { plugins: [router], stubs: elStubs },
    })
    expect(wrapper.find('.layout-shell-stub').exists()).toBe(true)
  })
})
