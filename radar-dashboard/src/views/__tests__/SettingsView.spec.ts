import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { useApiKeyStore } from '@/stores/apiKey'
import SettingsView from '../SettingsView.vue'

describe('SettingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('pre-fills the input with the currently stored key', () => {
    useApiKeyStore().setApiKey('existing-key')

    const wrapper = mount(SettingsView)

    expect((wrapper.find('input').element as HTMLInputElement).value).toBe('existing-key')
  })

  it('saves the typed key to the store and shows confirmation', async () => {
    const store = useApiKeyStore()
    const wrapper = mount(SettingsView)

    await wrapper.find('input').setValue('new-key')
    await wrapper.find('button').trigger('click')

    expect(store.apiKey).toBe('new-key')
    expect(wrapper.text()).toContain('Saved')
  })
})
