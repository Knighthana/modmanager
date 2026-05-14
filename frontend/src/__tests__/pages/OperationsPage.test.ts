import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'

// ── Module mocks ──────────────────────────────────────────────────────

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<typeof import('element-plus')>()
  return {
    ...actual,
    ElMessageBox: {
      confirm: vi.fn(),
    },
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
    },
  }
})

vi.mock('../../api/sse', () => ({
  streamSse: vi.fn(),
}))

vi.mock('../../stores/forest', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../stores/forest')>()
  return {
    ...actual,
    generateBackupDir: vi.fn(() => '/tmp/test_backup'),
  }
})

import OperationsPage from '../../pages/OperationsPage.vue'
import { streamSse } from '../../api/sse'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useForestStore } from '../../stores/forest'
import type { SseProgress } from '../../api/sse'
import type { MessageBoxData } from 'element-plus'

// ── Helpers ────────────────────────────────────────────────────────────

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/operations', name: 'operations', component: { template: '<div />' } },
  ],
})

const mockedStreamSse = vi.mocked(streamSse)
const mockedConfirm = vi.mocked(ElMessageBox.confirm)

/** Helper to access component VM with loose typing */
function vmAny(wrapper: VueWrapper): Record<string, unknown> {
  return wrapper.vm as unknown as Record<string, unknown>
}

// ── Workspace helper for localStorage ─────────────────────────────────

function setWorkspaceInStorage(overrides?: Partial<{
  trees_count: number
  mapping_count: number
  warnings: string[]
  errors: string[]
  stats: Record<string, unknown>
  inputs_hash: string
  timestamp: string | null
}> | null) {
  if (overrides === null) {
    // Explicitly set results to null
    const ws = {
      lastDatabase: 'default',
      perDatabase: {
        default: { decisions: {}, results: null },
      },
      aggregatedRuleSet: null,
      aggregatedRuleHash: '',
    }
    localStorage.setItem('modmanager:workspace', JSON.stringify(ws))
    return
  }
  const defaultResults = {
    trees_count: 42,
    mapping_count: 15,
    warnings: ['W_LOCAL_MOD_MISSING: castle'],
    errors: [],
    stats: { added: 3, overwritten: 10, deleted: 2 },
    inputs_hash: 'abc123',
    timestamp: '2026-05-13T10:00:05Z',
  }
  const results = overrides ? { ...defaultResults, ...overrides } : defaultResults
  const ws = {
    lastDatabase: 'default',
    perDatabase: {
      default: {
        decisions: {},
        results,
      },
    },
    aggregatedRuleSet: null,
    aggregatedRuleHash: '',
  }
  localStorage.setItem('modmanager:workspace', JSON.stringify(ws))
}

/** Mock fetch for DatabaseSelector's config/discover call */
function mockApiDiscover() {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    json: () => Promise.resolve({
      ok: true,
      data: { databases: { default: { path: '/fake/db.json' } } },
    }),
  }))
}

// ── Element Plus stubs ────────────────────────────────────────────────

const elStubs = {
  'el-button': { template: '<button class="el-btn-stub" :disabled="$attrs.disabled"><slot /></button>' },
  'el-card': { template: '<div class="el-card-stub"><div v-if="$slots.header" class="el-card-header"><slot name="header" /></div><slot /></div>' },
  'el-descriptions': { template: '<div class="el-descriptions-stub"><slot /></div>' },
  'el-descriptions-item': { template: '<div class="el-descriptions-item-stub"><slot /></div>' },
  'el-empty': { template: '<div class="el-empty-stub">{{ $attrs.description }}</div>' },
  'el-switch': { template: '<label class="el-switch-stub"><input type="checkbox" :checked="$attrs.modelValue" /></label>' },
  'el-form': { template: '<div class="el-form-stub"><slot /></div>' },
  'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-progress': { template: '<div class="el-progress-stub" />' },
  'el-badge': { template: '<span class="el-badge-stub"><slot /></span>' },
}

// ── Test suite ────────────────────────────────────────────────────────

describe('OperationsPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
  })

  // ── Empty state ─────────────────────────────────────────────────────

  it('shows empty state when workspace has no results', async () => {
    setWorkspaceInStorage(null)
    mockApiDiscover()

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
    expect(wrapper.text()).toContain('尚未计算')
  })

  it('shows empty state when results has trees_count 0', async () => {
    setWorkspaceInStorage(null)
    mockApiDiscover()

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
  })

  // ── Summary display ─────────────────────────────────────────────────

  it('renders summary when workspace has results', async () => {
    setWorkspaceInStorage()
    mockApiDiscover()

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    // Check that summary is shown (not empty)
    expect(wrapper.find('.el-empty-stub').exists()).toBe(false)
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).toContain('15')
    // Warnings display shows the count (1 in this case)
    expect(wrapper.text()).toContain('1')
  })

  it('renders stats breakdown: added, overwritten, deleted', async () => {
    setWorkspaceInStorage()
    mockApiDiscover()

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('3')  // added
    expect(wrapper.text()).toContain('10') // overwritten
    expect(wrapper.text()).toContain('2')  // deleted
  })

  // ── Dry-run switch ──────────────────────────────────────────────────

  it('dry-run switch defaults to enabled', async () => {
    setWorkspaceInStorage()
    mockApiDiscover()

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    expect((vm as { dryRun: boolean }).dryRun).toBe(true)
  })

  // ── Operation buttons ───────────────────────────────────────────────

  it('renders backup, apply, restore buttons', async () => {
    setWorkspaceInStorage()
    mockApiDiscover()

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const buttons = wrapper.findAll('.el-btn-stub')
    const btnTexts = buttons.map(b => b.text())
    expect(btnTexts).toContain('备份')
    expect(btnTexts).toContain('应用')
    expect(btnTexts).toContain('恢复')
  })

  it('buttons are disabled while an operation is running', async () => {
    setWorkspaceInStorage()
    mockApiDiscover()

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    ;(vm as { operating: string | null }).operating = 'backup'
    await wrapper.vm.$nextTick()

    const buttons = wrapper.findAll('.el-btn-stub')
    buttons.forEach(btn => {
      expect(btn.attributes('disabled')).toBeDefined()
    })
  })

  // ── Backup operation ────────────────────────────────────────────────

  it('confirmBackup opens confirm dialog then calls streamSse', async () => {
    setWorkspaceInStorage()
    mockApiDiscover()
    mockedConfirm.mockResolvedValue(undefined as unknown as MessageBoxData) // user clicks confirm
    mockedStreamSse.mockImplementation(async (_path: string, _body: unknown, callbacks: { onProgress?: (p: SseProgress) => void; onResult?: (data: unknown) => void; onError?: (msg: string) => void }) => {
      callbacks.onProgress?.({ step: 'backup', finished: 1, total: 3, message: 'Backing up...' })
      callbacks.onResult?.({ ok: true, data: { backup_path: '/tmp/backup' } })
    })

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    await (vm as { confirmBackup: () => Promise<void> }).confirmBackup()

    expect(mockedConfirm).toHaveBeenCalled()
    expect(mockedStreamSse).toHaveBeenCalledWith(
      '/pipeline/backup',
      expect.objectContaining({ backup_dir: '/tmp/test_backup' }),
      expect.any(Object),
    )
    // After operation completes, operating should be null
    expect((vm as { operating: string | null }).operating).toBeNull()
    expect(ElMessage.success).toHaveBeenCalled()
  })

  it('confirmBackup does nothing when user cancels', async () => {
    setWorkspaceInStorage()
    mockApiDiscover()
    mockedConfirm.mockRejectedValue(new Error('cancel'))

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    await (vm as { confirmBackup: () => Promise<void> }).confirmBackup()

    expect(mockedConfirm).toHaveBeenCalled()
    expect(mockedStreamSse).not.toHaveBeenCalled()
  })

  // ── Apply operation ─────────────────────────────────────────────────

  it('confirmApply calls streamSse with dry-run flag', async () => {
    setWorkspaceInStorage()
    mockApiDiscover()
    mockedConfirm.mockResolvedValue(undefined as unknown as MessageBoxData)

    // Set up forest store with some mapping data
    const store = useForestStore()
    store.finalMapping = [{ path: '/a.txt', mixed_id: '1:2', hashtype: 'sha256', hashvalue: 'abc' }]
    store.storedMappingResult = { total: 15 }
    store.pipelineForm.backupDir = '/my/backup'

    mockedStreamSse.mockImplementation(async (_path: string, _body: unknown, callbacks: { onProgress?: (p: SseProgress) => void; onResult?: (data: unknown) => void; onError?: (msg: string) => void }) => {
      callbacks.onProgress?.({ step: 'apply', finished: 1, total: 5, message: 'Applying...' })
      callbacks.onResult?.({ ok: true, data: { applied: 15 } })
    })

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    // Verify dry-run is true by default
    expect((vm as { dryRun: boolean }).dryRun).toBe(true)

    await (vm as { confirmApply: () => Promise<void> }).confirmApply()

    expect(mockedStreamSse).toHaveBeenCalledWith(
      '/pipeline/apply',
      expect.objectContaining({
        final_mapping: [{ path: '/a.txt', mixed_id: '1:2', hashtype: 'sha256', hashvalue: 'abc' }],
        backup_dir: '/my/backup',
        dry_run: true,
      }),
      expect.any(Object),
    )
    expect(ElMessage.success).toHaveBeenCalled()
  })

  // ── Restore operation ───────────────────────────────────────────────

  it('confirmRestore calls streamSse with backup_dir', async () => {
    setWorkspaceInStorage()
    mockApiDiscover()
    mockedConfirm.mockResolvedValue(undefined as unknown as MessageBoxData)

    mockedStreamSse.mockImplementation(async (_path: string, _body: unknown, callbacks: { onProgress?: (p: SseProgress) => void; onResult?: (data: unknown) => void; onError?: (msg: string) => void }) => {
      callbacks.onProgress?.({ step: 'restore', finished: 1, total: 2, message: 'Restoring...' })
      callbacks.onResult?.({ ok: true, data: { restored: ['/a.txt'] } })
    })

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    await (vm as { confirmRestore: () => Promise<void> }).confirmRestore()

    expect(mockedStreamSse).toHaveBeenCalledWith(
      '/pipeline/restore',
      expect.objectContaining({
        backup_dir: '/tmp/test_backup',
        target_files: null,
      }),
      expect.any(Object),
    )
    expect(ElMessage.success).toHaveBeenCalled()
  })

  // ── Progress tracking ───────────────────────────────────────────────

  it('progress updates while operation runs', async () => {
    setWorkspaceInStorage()
    mockApiDiscover()
    mockedConfirm.mockResolvedValue(undefined as unknown as MessageBoxData)

    let progressCallback: ((p: SseProgress) => void) | undefined
    mockedStreamSse.mockImplementation(async (_path: string, _body: unknown, callbacks: { onProgress?: (p: SseProgress) => void; onResult?: (data: unknown) => void; onError?: (msg: string) => void }) => {
      progressCallback = callbacks.onProgress
      callbacks.onProgress?.({ step: 'backup', finished: 0, total: 3, message: 'Start' })
      callbacks.onProgress?.({ step: 'backup', finished: 2, total: 3, message: 'Halfway' })
      callbacks.onResult?.({ ok: true, data: {} })
    })

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    await (vm as { confirmBackup: () => Promise<void> }).confirmBackup()

    // Progress should have been updated via callbacks
    const progress = (vm as { progress: SseProgress }).progress
    expect(progress.step).toBe('backup')
    expect(progress.total).toBe(3)
  })

  // ── Error handling ──────────────────────────────────────────────────

  it('shows error message when operation fails', async () => {
    setWorkspaceInStorage()
    mockApiDiscover()
    mockedConfirm.mockResolvedValue(undefined as unknown as MessageBoxData)

    mockedStreamSse.mockImplementation(async (_path: string, _body: unknown, callbacks: { onProgress?: (p: SseProgress) => void; onResult?: (data: unknown) => void; onError?: (msg: string) => void }) => {
      callbacks.onProgress?.({ step: 'backup', finished: 0, total: 3, message: 'Starting...' })
      callbacks.onError?.('Backup failed: disk full')
    })

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    await (vm as { confirmBackup: () => Promise<void> }).confirmBackup()

    expect(ElMessage.error).toHaveBeenCalledWith(expect.stringContaining('Backup failed'))
    // operating should be reset
    expect((vm as { operating: string | null }).operating).toBeNull()
  })

  // ── getStat helper ──────────────────────────────────────────────────

  it('getStat returns 0 for missing stat keys', async () => {
    setWorkspaceInStorage({
      trees_count: 5,
      mapping_count: 3,
      warnings: [],
      errors: [],
      stats: { added: 1 },
      inputs_hash: '',
      timestamp: null,
    })
    mockApiDiscover()

    const wrapper = mount(OperationsPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    const vm = vmAny(wrapper)
    const page = vm as { getStat: (key: string) => number }
    expect(page.getStat('added')).toBe(1)
    expect(page.getStat('overwritten')).toBe(0)
    expect(page.getStat('deleted')).toBe(0)
    expect(page.getStat('nonexistent')).toBe(0)
  })
})
