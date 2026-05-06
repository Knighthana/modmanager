import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useForestStore } from '../../stores/forest'

describe('useForestStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initialises with empty state', () => {
    const store = useForestStore()
    expect(store.trees).toEqual([])
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
    // conflictList is computed from trees with resolved_state === 'pending'
    store.trees = [
      { root_path: '/a.png', destin_mixed_id: 'mod:A', changerequest: [], refs: [], resolved_state: 'pending', candidates: ['/m1/a.png', '/m2/a.png'] },
      { root_path: '/b.png', destin_mixed_id: 'mod:B', changerequest: [], refs: [], resolved_state: 'pending', candidates: ['/m1/b.png'] },
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
    store.trees = [{ root_path: '/a.png', destin_mixed_id: 'mod:A', changerequest: [], refs: [], resolved_state: 'kept' }]
    store.errors = ['some error']
    store.branchDecisions = { '/a.png': '/m1/a.png' }
    store.reset()
    expect(store.trees).toEqual([])
    expect(store.errors).toEqual([])
    expect(store.branchDecisions).toEqual({})
  })

  it('isClean returns true when no errors and no unresolved conflicts', () => {
    const store = useForestStore()
    expect(store.isClean).toBe(true)

    store.errors.push('error')
    expect(store.isClean).toBe(false)

    store.errors = []
    store.trees = [{ root_path: '/a.png', destin_mixed_id: 'mod:A', changerequest: [], refs: [], resolved_state: 'pending', candidates: ['/m1/a.png'] }]
    expect(store.isClean).toBe(false)
  })

  it('conflictList filters trees with pending resolved_state', () => {
    const store = useForestStore()
    store.trees = [
      { root_path: '/kept.png', destin_mixed_id: 'mod:A', changerequest: [], refs: [], resolved_state: 'kept' },
      { root_path: '/pending.png', destin_mixed_id: 'mod:B', changerequest: [], refs: [], resolved_state: 'pending', candidates: ['/m1/p.png'] },
      { root_path: '/deleted.png', destin_mixed_id: 'mod:C', changerequest: [], refs: [], resolved_state: 'deleted' },
    ]
    expect(store.conflictList).toHaveLength(1)
    expect(store.conflictList[0].root_path).toBe('/pending.png')
    expect(store.conflictList[0].candidates).toEqual(['/m1/p.png'])
  })
})
