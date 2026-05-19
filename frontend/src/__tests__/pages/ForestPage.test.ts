import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
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
    return mount(ForestPage, {
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

  it('toggles minimap visibility on button click', async () => {
    await router.push('/workspace/test-ws-1/forest')
    const wrapper = createWrapper()

    // Initially minimap is shown
    const viewer = wrapper.findComponent({ name: 'ForestViewer' })
    expect(viewer.exists()).toBe(true)
    expect(viewer.props('showMinimap')).toBe(true)

    // Click the toggle button → hidden
    const btn = wrapper.find('.forest-controls button:nth-child(2)')
    await btn.trigger('click')
    expect(viewer.props('showMinimap')).toBe(false)

    // Click again → shown
    await btn.trigger('click')
    expect(viewer.props('showMinimap')).toBe(true)
  })
})
