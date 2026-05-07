import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPersistence } from '../../utils/persistence'

describe('createPersistence', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('save stores value with modmanager: prefix', () => {
    const pers = createPersistence()
    pers.save('test-key', { foo: 'bar' })

    const raw = localStorage.getItem('modmanager:test-key')
    expect(raw).not.toBeNull()
    expect(JSON.parse(raw!)).toEqual({ foo: 'bar' })
  })

  it('load retrieves previously saved value', () => {
    const pers = createPersistence()
    pers.save('test-key', { num: 42 })

    const loaded = pers.load<{ num: number }>('test-key')
    expect(loaded).not.toBeNull()
    expect(loaded!.num).toBe(42)
  })

  it('load returns null for missing key', () => {
    const pers = createPersistence()
    const loaded = pers.load('nonexistent')
    expect(loaded).toBeNull()
  })

  it('load returns null for invalid JSON', () => {
    localStorage.setItem('modmanager:bad', 'not-json{')
    const pers = createPersistence()
    const loaded = pers.load('bad')
    expect(loaded).toBeNull()
  })

  it('clear removes the key', () => {
    const pers = createPersistence()
    pers.save('test-key', 'value')
    expect(pers.load('test-key')).toBe('value')

    pers.clear('test-key')
    expect(pers.load('test-key')).toBeNull()
  })

  it('clear does not affect other keys', () => {
    const pers = createPersistence()
    pers.save('key-a', 'a')
    pers.save('key-b', 'b')

    pers.clear('key-a')
    expect(pers.load('key-a')).toBeNull()
    expect(pers.load('key-b')).toBe('b')
  })

  it('save overwrites existing value', () => {
    const pers = createPersistence()
    pers.save('test-key', 'old')
    pers.save('test-key', 'new')

    expect(pers.load('test-key')).toBe('new')
  })
})
