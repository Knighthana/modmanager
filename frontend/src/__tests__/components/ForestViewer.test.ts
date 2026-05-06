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

// Stub for el-card
const elCardStub = {
  name: 'ElCard',
  template: '<div class="el-card-stub"><slot /></div>',
  props: {
    shadow: String,
  },
}

describe('ForestViewer', () => {
  it('renders SVG content via v-html', () => {
    setActivePinia(createPinia())
    const store = useForestStore()
    store.svgContent = '<svg><g id="test"><text>Hello SVG</text></g></svg>'

    const wrapper = mount(ForestViewer, {
      global: {
        plugins: [router],
        stubs: {
          'el-card': elCardStub,
        },
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
        stubs: {
          'el-card': elCardStub,
        },
      },
    })

    // When no SVG and not running, the empty state text is shown
    expect(wrapper.text()).toContain('暂无森林图')
  })

  it('renders loading state when isRunning is true', () => {
    setActivePinia(createPinia())
    const store = useForestStore()
    store.isRunning = true

    const wrapper = mount(ForestViewer, {
      global: {
        plugins: [router],
        stubs: {
          'el-card': elCardStub,
          'v-loading': false,
        },
      },
    })

    // When isRunning is true, the empty state is hidden (v-if checks !store.isRunning)
    // and SVG content is empty, so neither empty state nor SVG div is shown
    // The component renders the el-card wrapper with loading directive
    expect(wrapper.find('.el-card-stub').exists()).toBe(true)
  })
})
