import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useApiKeyStore } from '../apiKey'

const STORAGE_KEY = 'radar-dashboard/api-key'

describe('apiKey store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
  })

  it('starts empty when nothing is stored', () => {
    const store = useApiKeyStore()

    expect(store.apiKey).toBe('')
  })

  it('reads a previously stored key on creation', () => {
    sessionStorage.setItem(STORAGE_KEY, 'previous-key')

    const store = useApiKeyStore()

    expect(store.apiKey).toBe('previous-key')
  })

  it('setApiKey updates the store and sessionStorage', () => {
    const store = useApiKeyStore()

    store.setApiKey('new-key')

    expect(store.apiKey).toBe('new-key')
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe('new-key')
  })

  it('setApiKey with an empty string clears sessionStorage', () => {
    const store = useApiKeyStore()
    store.setApiKey('new-key')

    store.setApiKey('')

    expect(store.apiKey).toBe('')
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
