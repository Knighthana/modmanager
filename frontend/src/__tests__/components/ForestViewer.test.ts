import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import ForestViewer from '../../components/ForestViewer.vue'
import { useForestStore } from '../../stores/forest'

/**
 * Helper: find a DOM element by its data-tree-node attribute value.
 * Uses native DOM querySelectorAll + filter, because attribute values may contain
 * special CSS characters (/, .) that require escaping.
 */
function findNodeByPath(container: HTMLElement, path: string): HTMLElement | null {
  const nodes = container.querySelectorAll<HTMLElement>('[data-tree-node]')
  for (const n of nodes) {
    if (n.getAttribute('data-tree-node') === path) return n
  }
  return null
}

// Shared SVG content with nodes having refs/referenced-by relationships
const svgWithRelationships = `
<svg>
  <g data-tree-node="/a.png" data-tree-refs="/b.png" data-tree-referenced-by="">
    <text>A</text>
  </g>
  <g data-tree-node="/b.png" data-tree-refs="" data-tree-referenced-by="/a.png">
    <text>B</text>
  </g>
  <g data-tree-node="/c.png" data-tree-refs="" data-tree-referenced-by="">
    <text>C</text>
  </g>
  <g data-tree-node="/pending.png" data-tree-pending="true" data-tree-refs="" data-tree-referenced-by="">
    <text>Pending</text>
  </g>
</svg>
`

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

  it('test_hover_highlights_refs', async () => {
    setActivePinia(createPinia())
    const store = useForestStore()
    store.svgContent = svgWithRelationships

    const wrapper = mount(ForestViewer, {
      global: {
        plugins: [router],
        stubs: { 'el-card': elCardStub },
      },
    })

    // Wait for render
    await wrapper.vm.$nextTick()

    const containerEl = wrapper.find('.forest-container').element as HTMLElement

    const nodeA = findNodeByPath(containerEl, '/a.png')!
    const nodeB = findNodeByPath(containerEl, '/b.png')!
    const nodeC = findNodeByPath(containerEl, '/c.png')!

    // Hover over node A (which refs B and is referenced-by nothing)
    nodeA.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
    await wrapper.vm.$nextTick()

    // Node A (self) and node B (ref) should remain opaque
    expect(nodeA.style.opacity).toBe('1')
    expect(nodeB.style.opacity).toBe('1')
    // Node C (unrelated) should be dimmed
    expect(nodeC.style.opacity).toBe('0.15')

    // Mouse out of the container
    containerEl.dispatchEvent(new MouseEvent('mouseout', { bubbles: true }))
    await wrapper.vm.$nextTick()

    // All nodes restored to full opacity
    expect(nodeA.style.opacity).toBe('1')
    expect(nodeB.style.opacity).toBe('1')
    expect(nodeC.style.opacity).toBe('1')
  })

  it('test_click_pending_enters_selection_mode', async () => {
    setActivePinia(createPinia())
    const store = useForestStore()
    store.svgContent = svgWithRelationships

    const wrapper = mount(ForestViewer, {
      global: {
        plugins: [router],
        stubs: { 'el-card': elCardStub },
      },
    })

    await wrapper.vm.$nextTick()

    const containerEl = wrapper.find('.forest-container').element as HTMLElement
    const pendingNode = findNodeByPath(containerEl, '/pending.png')!

    // Click pending tree → enter selection mode
    pendingNode.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await wrapper.vm.$nextTick()

    expect(pendingNode.classList.contains('selected')).toBe(true)

    // Click same pending tree again → cancel selection
    pendingNode.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await wrapper.vm.$nextTick()

    expect(pendingNode.classList.contains('selected')).toBe(false)
  })

  it('test_click_source_in_selection_mode_sets_decision', async () => {
    setActivePinia(createPinia())
    const store = useForestStore()
    store.svgContent = svgWithRelationships
    // Provide matching tree data so the click handler can look up candidates
    store.trees = [
      {
        root_path: '/pending.png',
        destin_mixed_id: 'mod:P',
        changerequest: [],
        refs: [],
        resolved_state: 'pending',
        candidates: ['/a.png'],
      },
    ]

    const wrapper = mount(ForestViewer, {
      global: {
        plugins: [router],
        stubs: { 'el-card': elCardStub },
      },
    })

    await wrapper.vm.$nextTick()

    const containerEl = wrapper.find('.forest-container').element as HTMLElement
    const pendingNode = findNodeByPath(containerEl, '/pending.png')!
    const sourceNode = findNodeByPath(containerEl, '/a.png')!

    // Click pending tree to enter selection mode
    pendingNode.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await wrapper.vm.$nextTick()
    expect(pendingNode.classList.contains('selected')).toBe(true)

    // Spy on store.setDecision AFTER entering selection mode
    const setDecisionSpy = vi.spyOn(store, 'setDecision')

    // Click candidate source node while in selection mode
    sourceNode.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await wrapper.vm.$nextTick()

    // setDecision should have been called with (pending_root, source_path)
    expect(setDecisionSpy).toHaveBeenCalledWith('/pending.png', '/a.png')

    // Selection should be cleared after decision
    expect(pendingNode.classList.contains('selected')).toBe(false)
  })
})
