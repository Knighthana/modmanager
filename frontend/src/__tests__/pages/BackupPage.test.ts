import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

// Mock API client and SSE
vi.mock('../../api/client', () => ({
  apiPost: vi.fn(),
}))

vi.mock('../../api/sse', () => ({
  streamSse: vi.fn(),
}))

import BackupPage from '../../pages/BackupPage.vue'
import { apiPost } from '../../api/client'
import { streamSse } from '../../api/sse'
import type { ApiResponse } from '../../api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/backups', name: 'backups', component: { template: '<div />' } },
  ],
})

// Element Plus stubs
const elStubs = {
  'el-button': { template: '<button class="el-btn-stub" :disabled="$attrs.disabled"><slot /></button>' },
  'el-input': { template: '<input class="el-input-stub" />' },
  'el-form': { template: '<form class="el-form-stub"><slot /></form>' },
  'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-card': { template: '<div class="el-card-stub"><slot /><div v-if="$slots.header" class="el-card-header"><slot name="header" /></div></div>' },
  'el-table': { template: '<div class="el-table-stub"><slot /></div>' },
  'el-table-column': { template: '<div class="el-table-column-stub"><slot /></div>' },
  'el-empty': { template: '<div class="el-empty-stub">{{ $attrs.description }}</div>' },
  'el-dialog': { template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>' },
  'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
}

const mockedApiPost = vi.mocked(apiPost)
const mockedStreamSse = vi.mocked(streamSse)

// Helper to get vm as any for accessing internal component state
function vmAny(wrapper: VueWrapper): Record<string, unknown> {
  return wrapper.vm as unknown as Record<string, unknown>
}

describe('BackupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the form with input and scan button', () => {
    const wrapper = mount(BackupPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    expect(wrapper.text()).toContain('备份管理')
    expect(wrapper.find('.el-input-stub').exists()).toBe(true)
    expect(wrapper.find('.el-btn-stub').exists()).toBe(true)
  })

  it('shows empty state before scanning', () => {
    const wrapper = mount(BackupPage, {
      global: { plugins: [router], stubs: elStubs },
    })
    expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
  })

  it('onScan calls /backups/list API and updates backupDirs ref', async () => {
    const apiResp: ApiResponse<{ backups: Array<{ name: string; path: string; file_count: number }> }> = {
      ok: true,
      data: {
        backups: [
          { name: 'kmmbackup_001', path: '/backups/kmmbackup_001', file_count: 5 },
          { name: 'kmmbackup_002', path: '/backups/kmmbackup_002', file_count: 3 },
        ],
      },
      errors: [],
      warnings: [],
    }
    mockedApiPost.mockResolvedValue(apiResp)

    const wrapper = mount(BackupPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    // Set form value via vm
    const vm = vmAny(wrapper)
    const form = vm.form as { backupDir: string }
    form.backupDir = '/backups'
    await (vm as { onScan: () => Promise<void> }).onScan()
    await wrapper.vm.$nextTick()

    // Verify API was called correctly
    expect(mockedApiPost).toHaveBeenCalledWith('/backups/list', { dir: '/backups' })

    // Verify internal ref was updated (access via vm for the ref array)
    const backupDirs = (vm as unknown as { backupDirs: Array<{ name: string }> }).backupDirs
    expect(backupDirs.length).toBe(2)
    expect(backupDirs[0].name).toBe('kmmbackup_001')
  })

  it('onInspect calls /backups/inspect API and updates inspectResult', async () => {
    // First scan
    const scanResp: ApiResponse<{ backups: Array<{ name: string; path: string; file_count: number }> }> = {
      ok: true,
      data: { backups: [{ name: 'kmmbackup_test', path: '/bak/kmmbackup_test', file_count: 2 }] },
      errors: [],
      warnings: [],
    }
    mockedApiPost.mockResolvedValueOnce(scanResp)

    const wrapper = mount(BackupPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper)
    const form = vm.form as { backupDir: string }
    form.backupDir = '/bak'
    await (vm as { onScan: () => Promise<void> }).onScan()
    await wrapper.vm.$nextTick()

    // Mock inspect response
    const inspectResp: ApiResponse<{
      path: string
      file_count: number
      files: Array<{ relpath: string; hash: string }>
      dirty: { dirty: boolean; errors: string[]; partial_files: string[] }
      conflicts: { clean: boolean; conflicts: string[] }
    }> = {
      ok: true,
      data: {
        path: '/bak/kmmbackup_test',
        file_count: 2,
        files: [{ relpath: 'mnt/d/test.txt', hash: 'abc123' }],
        dirty: { dirty: false, errors: [], partial_files: [] },
        conflicts: { clean: true, conflicts: [] },
      },
      errors: [],
      warnings: [],
    }
    mockedApiPost.mockResolvedValueOnce(inspectResp)

    // Call inspect
    const page = vm as unknown as {
      onInspect: (row: { name: string; path: string; file_count: number }) => Promise<void>
      inspectResult: { path: string; dirty: { dirty: boolean }; conflicts: { clean: boolean } } | null
    }
    await page.onInspect({ name: 'kmmbackup_test', path: '/bak/kmmbackup_test', file_count: 2 })
    await wrapper.vm.$nextTick()

    expect(mockedApiPost).toHaveBeenCalledWith('/backups/inspect', { path: '/bak/kmmbackup_test' })
    // Verify internal ref was updated
    expect(page.inspectResult).not.toBeNull()
    expect(page.inspectResult!.path).toBe('/bak/kmmbackup_test')
    expect(page.inspectResult!.dirty.dirty).toBe(false)
    expect(page.inspectResult!.conflicts.clean).toBe(true)
  })

  it('confirmRestore opens dialog', async () => {
    const wrapper = mount(BackupPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper)
    const page = vm as unknown as {
      confirmRestore: (row: { name: string; path: string }) => void
      restoreDialogVisible: boolean
      restoreTargetPath: string
    }
    await page.confirmRestore({ name: 'kmmbackup_test', path: '/bak/kmmbackup_test' })
    await wrapper.vm.$nextTick()

    expect(page.restoreDialogVisible).toBe(true)
    expect(page.restoreTargetPath).toBe('/bak/kmmbackup_test')
  })

  it('doRestore calls /pipeline/restore via SSE', async () => {
    mockedStreamSse.mockImplementation(async (_path: string, _body: unknown, callbacks: { onProgress?: (p: { step: string; finished: number; total: number; message: string }) => void; onResult?: (data: unknown) => void; onError?: (msg: string) => void }) => {
      callbacks.onProgress?.({ step: 'restoring', finished: 1, total: 3, message: 'Working' })
      callbacks.onResult?.({ ok: true, data: { restored: ['/mnt/d/test.txt'], skipped: [], errors: [], orphans: [] } })
    })

    const wrapper = mount(BackupPage, {
      global: { plugins: [router], stubs: elStubs },
    })

    const vm = vmAny(wrapper)
    const page = vm as unknown as {
      restoreTargetPath: string
      doRestore: () => Promise<void>
    }
    page.restoreTargetPath = '/bak/kmmbackup_test'
    await page.doRestore()
    await wrapper.vm.$nextTick()

    expect(mockedStreamSse).toHaveBeenCalledWith(
      '/pipeline/restore',
      { backup_dir: '/bak/kmmbackup_test', target_files: null },
      expect.any(Object),
    )
  })
})
