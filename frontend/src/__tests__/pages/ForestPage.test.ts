import { describe, it, expect, beforeEach, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import ForestPage from '../../pages/ForestPage.vue'

// Stub router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/forest', name: 'forest', component: { template: '<div />' } },
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

  it('renders the page title', () => {
    const wrapper = createWrapper()
    expect(wrapper.find('h2').text()).toBe('Forest 可视化')
  })
})
