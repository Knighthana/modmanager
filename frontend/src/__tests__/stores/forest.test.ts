import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useForestStore } from '../../stores/forest'

describe('useForestStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initialises with empty state', () => {
    const store = useForestStore()
    expect(store.forest).toEqual([])
    expect(store.finalMapping).toEqual([])
    expect(store.conflictList).toEqual([])
    expect(store.branchDecisions).toEqual({})
    expect(store.errors).toEqual([])
    expect(store.warnings).toEqual([])
    expect(store.svgContent).toBe('')
    expect(store.isRunning).toBe(false)
    expect(store.progress).toEqual({ step: '', finished: 0, total: -1, message: '' })
  })

  it('unresolvedCount returns number of conflicts without decisions', () => {
    const store = useForestStore()
    store.conflictList = [
      { target: '/a.png', destin_mixed_id: 'mod:A', candidates: ['/m1/a.png', '/m2/a.png'] },
      { target: '/b.png', destin_mixed_id: 'mod:B', candidates: ['/m1/b.png'] },
    ]
    expect(store.unresolvedCount).toBe(2)

    store.setDecision('/a.png', '/m1/a.png')
    expect(store.unresolvedCount).toBe(1)

    store.setDecision('/b.png', '/m1/b.png')
    expect(store.unresolvedCount).toBe(0)
  })

  it('setDecision stores the branch decision', () => {
    const store = useForestStore()
    store.setDecision('/x.png', '/mod/x.png')
    expect(store.branchDecisions['/x.png']).toBe('/mod/x.png')
  })

  it('clearDecisions removes all branch decisions', () => {
    const store = useForestStore()
    store.setDecision('/a.png', '/m1/a.png')
    store.setDecision('/b.png', '/m1/b.png')
    expect(Object.keys(store.branchDecisions).length).toBe(2)
    store.clearDecisions()
    expect(store.branchDecisions).toEqual({})
  })

  it('reset clears all data', () => {
    const store = useForestStore()
    store.forest = [{ path: '/a.png', destin_mixed_id: 'mod:A', changerequest: [] }]
    store.errors = ['some error']
    store.branchDecisions = { '/a.png': '/m1/a.png' }
    store.reset()
    expect(store.forest).toEqual([])
    expect(store.errors).toEqual([])
    expect(store.branchDecisions).toEqual({})
  })

  it('isClean returns true when no errors and no unresolved conflicts', () => {
    const store = useForestStore()
    expect(store.isClean).toBe(true)

    store.errors.push('error')
    expect(store.isClean).toBe(false)

    store.errors = []
    store.conflictList = [{ target: '/a.png', destin_mixed_id: 'mod:A', candidates: ['/m1/a.png'] }]
    expect(store.isClean).toBe(false)
  })
})
