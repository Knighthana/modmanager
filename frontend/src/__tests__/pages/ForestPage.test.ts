import { describe, it, expect, beforeEach, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import ForestPage from '../../pages/ForestPage.vue'

// Stub router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/workspace/:workspaceId/forest', name: 'workspace-forest', component: { template: '<div />' } },
  ],
})

describe('ForestPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function createWrapper() {
    return shallowMount(ForestPage, {
      global: {
        plugins: [router],
      },
    })
  }

  it('renders the page title', async () => {
    await router.push('/workspace/test-ws-1/forest')
    const wrapper = createWrapper()
    expect(wrapper.find('.forest-page').exists()).toBe(true)
  })
})
