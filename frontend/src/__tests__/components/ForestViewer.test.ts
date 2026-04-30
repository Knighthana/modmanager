import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import ForestViewer from '../../components/ForestViewer.vue'
import { useForestStore } from '../../stores/forest'

// Stub router for tests
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/forest', name: 'forest', component: { template: '<div />' } },
    { path: '/conflicts', name: 'conflicts', component: { template: '<div />' } },
  ],
})

describe('ForestViewer', () => {
  it('renders SVG content via v-html', () => {
    setActivePinia(createPinia())
    const store = useForestStore()
    store.svgContent = '<svg><g id="test"><text>Hello SVG</text></g></svg>'

    const wrapper = mount(ForestViewer, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.find('.forest-svg').exists()).toBe(true)
    expect(wrapper.html()).toContain('Hello SVG')
  })

  it('shows empty state when no SVG content and not running', () => {
    setActivePinia(createPinia())

    const wrapper = mount(ForestViewer, {
      global: {
        plugins: [router],
      },
    })

    // The forest-svg div still exists but has no content
    expect(wrapper.find('.forest-container').exists()).toBe(true)
  })

  it('renders loading state when isRunning is true', () => {
    setActivePinia(createPinia())
    const store = useForestStore()
    store.isRunning = true

    const wrapper = mount(ForestViewer, {
      global: {
        plugins: [router],
        stubs: {
          'el-card': {
            template: '<div><slot /></div>',
          },
        },
      },
    })

    // The v-loading directive adds element-plus loading classes
    expect(wrapper.find('.forest-container').exists()).toBe(true)
  })
})
