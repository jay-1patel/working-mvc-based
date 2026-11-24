import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest'
import { fixtureServer } from './fixture-server'
import { testState } from './fixture-server'

// Node 26 exposes a broken global localStorage unless --localstorage-file is
// set; that shadows jsdom's implementation and makes auth persistence a no-op.
if (typeof globalThis.localStorage === 'undefined' || typeof globalThis.localStorage?.getItem !== 'function') {
  const store = new Map<string, string>()
  const memoryStorage: Storage = {
    get length() {
      return store.size
    },
    clear() {
      store.clear()
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null
    },
    key(index: number) {
      return [...store.keys()][index] ?? null
    },
    removeItem(key: string) {
      store.delete(key)
    },
    setItem(key: string, value: string) {
      store.set(String(key), String(value))
    },
  }
  Object.defineProperty(globalThis, 'localStorage', {
    value: memoryStorage,
    writable: true,
    configurable: true,
  })
}

beforeEach(() => {
  testState.reset()
  try {
    globalThis.localStorage?.clear?.()
  } catch {
    /* ignore */
  }
})

afterEach(() => {
  cleanup()
})

beforeAll(() => {
  fixtureServer.install()
})

afterAll(() => {
  fixtureServer.restore()
})
