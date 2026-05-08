import { describe, it, expect, beforeEach, vi } from 'vitest'
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
    expect(store.lastSuccessfulParams).toBeNull()
  })

  it('unresolvedCount returns number of conflicts without decisions', () => {
    const store = useForestStore()
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

  it('reset clears output data but preserves branchDecisions', () => {
    const store = useForestStore()
    store.trees = [{ root_path: '/a.png', destin_mixed_id: 'mod:A', changerequest: [], refs: [], resolved_state: 'kept' }]
    store.errors = ['some error']
    store.branchDecisions = { '/a.png': '/m1/a.png' }
    store.lastSuccessfulParams = {
      database: { steamlib: [] },
      kmm_rule_paths: ['/rules.json'],
      user_config_path: '/cfg.json',
      backup_dir: '/backups',
      dry_run: true,
    }
    store.reset()
    expect(store.trees).toEqual([])
    expect(store.errors).toEqual([])
    // branchDecisions survives reset (TODO-8: persist across recompute)
    expect(store.branchDecisions).toEqual({ '/a.png': '/m1/a.png' })
    expect(store.lastSuccessfulParams).toBeNull()
  })

  it('branchDecisions survives multiple reset calls', () => {
    const store = useForestStore()
    store.setDecision('/a.png', '/m1/a.png')
    store.setDecision('/b.png', '/m2/b.png')
    expect(Object.keys(store.branchDecisions).length).toBe(2)

    // First reset — decisions survive
    store.reset()
    expect(store.branchDecisions).toEqual({ '/a.png': '/m1/a.png', '/b.png': '/m2/b.png' })

    // Second reset — still survive
    store.reset()
    expect(store.branchDecisions).toEqual({ '/a.png': '/m1/a.png', '/b.png': '/m2/b.png' })

    // clearDecisions still works explicitly
    store.clearDecisions()
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

  // ── G1-01 / G1-02: lastSuccessfulParams ────────────────────────────────

  it('lastSuccessfulParams starts null', () => {
    const store = useForestStore()
    expect(store.lastSuccessfulParams).toBeNull()
  })

  it('runPipeline stores lastSuccessfulParams on result with ok=true', async () => {
    // Mock fetch to simulate SSE result
    const mockFetch = vi.fn()
    vi.stubGlobal('fetch', mockFetch)

    const sseChunks = [
      'event: result\ndata: {"ok":true,"data":{"trees":[],"final_mapping":[],"mapping_result":{}},"errors":[],"warnings":[]}\n\n',
    ]
    const encoder = new TextEncoder()
    mockFetch.mockResolvedValue({
      ok: true,
      body: {
        getReader() {
          let idx = 0
          return {
            read() {
              if (idx >= sseChunks.length) {
                return Promise.resolve({ done: true, value: undefined })
              }
              return Promise.resolve({ done: false, value: encoder.encode(sseChunks[idx++]) })
            },
          }
        },
      },
    })

    const store = useForestStore()
    const params = {
      database: { steamlib: [] },
      kmm_rule_paths: ['/rules.json'],
      user_config_path: '/cfg.json',
      backup_dir: '/backups',
      dry_run: true,
    }
    await store.runPipeline(params)

    expect(store.lastSuccessfulParams).not.toBeNull()
    expect(store.lastSuccessfulParams!.database).toEqual({ steamlib: [] })
    expect(store.lastSuccessfulParams!.kmm_rule_paths).toEqual(['/rules.json'])
  })

  it('computeOnly stores lastSuccessfulParams on result with ok=true', async () => {
    const mockFetch = vi.fn()
    vi.stubGlobal('fetch', mockFetch)

    const sseChunks = [
      'event: result\ndata: {"ok":true,"data":{"trees":[],"final_mapping":[],"mapping_result":{}},"errors":[],"warnings":[]}\n\n',
    ]
    const encoder = new TextEncoder()
    mockFetch.mockResolvedValue({
      ok: true,
      body: {
        getReader() {
          let idx = 0
          return {
            read() {
              if (idx >= sseChunks.length) {
                return Promise.resolve({ done: true, value: undefined })
              }
              return Promise.resolve({ done: false, value: encoder.encode(sseChunks[idx++]) })
            },
          }
        },
      },
    })

    const store = useForestStore()
    const params = {
      database: { steamlib: [] },
      kmm_rule_paths: ['/rules.json'],
      user_config_path: '/cfg.json',
      backup_dir: null,
      dry_run: true,
    }
    await store.computeOnly(params)

    expect(store.lastSuccessfulParams).not.toBeNull()
    expect(store.lastSuccessfulParams!.kmm_rule_paths).toEqual(['/rules.json'])
  })

  // ── B1-01 / B1-02: discoverDatabase / loadConfig split ──────────────────

  it('discoverDatabase does NOT call config endpoints (no side effect)', async () => {
    const mockFetch = vi.fn()
    vi.stubGlobal('fetch', mockFetch)

    // Only the database/generate SSE endpoint
    const sseChunks = [
      'event: result\ndata: {"ok":true,"data":{"steamlib":[],"game":[],"mod":[]},"errors":[],"warnings":[]}\n\n',
    ]
    const encoder = new TextEncoder()
    mockFetch.mockResolvedValue({
      ok: true,
      body: {
        getReader() {
          let idx = 0
          return {
            read() {
              if (idx >= sseChunks.length) {
                return Promise.resolve({ done: true, value: undefined })
              }
              return Promise.resolve({ done: false, value: encoder.encode(sseChunks[idx++]) })
            },
          }
        },
      },
    })

    const store = useForestStore()
    // discoverDatabase now reads from pipelineForm internally
    store.pipelineForm.discoveryMode = 'auto'
    store.pipelineForm.workingPathstyle = 'linux'
    store.pipelineForm.greedyParsing = false
    store.pipelineForm.cachePath = '/tmp/db.json'
    await store.discoverDatabase()

    // After discoverDatabase, databaseSummary should be set
    expect(store.databaseSummary).not.toBeNull()
    // But userConfig should NOT be set (loadConfig was not called)
    expect(store.userConfig).toBeNull()
    // Only 1 fetch call (database/generate, no config calls)
    expect(mockFetch.mock.calls.length).toBe(1)
  })

  it('loadConfig fetches and saves user_config', async () => {
    let callCount = 0
    const mockFetch = vi.fn()
    vi.stubGlobal('fetch', mockFetch)

    // /config/discover returns config
    // /config/save returns ok
    mockFetch.mockImplementation(async (url: string) => {
      callCount++
      if (url.includes('/config/discover')) {
        return {
          ok: true,
          json: async () => ({ ok: true, data: { game: 'valheim' }, errors: [], warnings: [] }),
        }
      }
      if (url.includes('/config/save')) {
        return {
          ok: true,
          json: async () => ({ ok: true, data: { saved: '/tmp/userconfig.json' }, errors: [], warnings: [] }),
        }
      }
      return { ok: true, json: async () => ({ ok: true, data: {} }), body: null }
    })

    const store = useForestStore()
    await store.loadConfig()

    expect(store.userConfig).not.toBeNull()
    expect(store.userConfig!.game).toBe('valheim')
    // Should have called both discover and save
    expect(callCount).toBeGreaterThanOrEqual(2)
  })

  // ── M1-05: mode switching tests ─────────────────────────────────────────

  it('default mode is auto, discoverDatabase sends mode=auto with paths=null', async () => {
    const mockFetch = vi.fn()
    vi.stubGlobal('fetch', mockFetch)

    const sseChunks = [
      'event: result\ndata: {"ok":true,"data":{"steamlib":[],"game":[],"mod":[]},"errors":[],"warnings":[]}\n\n',
    ]
    const encoder = new TextEncoder()
    mockFetch.mockResolvedValue({
      ok: true,
      body: {
        getReader() {
          let idx = 0
          return {
            read() {
              if (idx >= sseChunks.length) {
                return Promise.resolve({ done: true, value: undefined })
              }
              return Promise.resolve({ done: false, value: encoder.encode(sseChunks[idx++]) })
            },
          }
        },
      },
    })

    const store = useForestStore()
    expect(store.pipelineForm.discoveryMode).toBe('auto')

    // Set form fields via pipelineForm so discoverDatabase picks them up
    store.pipelineForm.workingPathstyle = 'linux'
    store.pipelineForm.greedyParsing = false
    store.pipelineForm.cachePath = '/tmp/db.json'
    await store.discoverDatabase()

    // Verify that fetch was called with mode='auto' and paths=null
    const callUrl = mockFetch.mock.calls[0][0]
    const callBody = JSON.parse(mockFetch.mock.calls[0][1].body)
    expect(callUrl).toContain('/database/generate')
    expect(callBody.mode).toBe('auto')
    expect(callBody.paths).toBeNull()
  })

  it('manual mode sends mode=manual with paths=[input path]', async () => {
    const mockFetch = vi.fn()
    vi.stubGlobal('fetch', mockFetch)

    const sseChunks = [
      'event: result\ndata: {"ok":true,"data":{"steamlib":[],"game":[],"mod":[]},"errors":[],"warnings":[]}\n\n',
    ]
    const encoder = new TextEncoder()
    mockFetch.mockResolvedValue({
      ok: true,
      body: {
        getReader() {
          let idx = 0
          return {
            read() {
              if (idx >= sseChunks.length) {
                return Promise.resolve({ done: true, value: undefined })
              }
              return Promise.resolve({ done: false, value: encoder.encode(sseChunks[idx++]) })
            },
          }
        },
      },
    })

    const store = useForestStore()
    store.pipelineForm.discoveryMode = 'manual'
    store.pipelineForm.manualSteamPath = '/tmp/fixture/steamapps'
    store.pipelineForm.workingPathstyle = 'linux'
    store.pipelineForm.greedyParsing = false
    store.pipelineForm.cachePath = '/tmp/db.json'
    await store.discoverDatabase()

    const callUrl = mockFetch.mock.calls[0][0]
    const callBody = JSON.parse(mockFetch.mock.calls[0][1].body)
    expect(callUrl).toContain('/database/generate')
    expect(callBody.mode).toBe('manual')
    expect(callBody.paths).toEqual(['/tmp/fixture/steamapps'])
  })
})
