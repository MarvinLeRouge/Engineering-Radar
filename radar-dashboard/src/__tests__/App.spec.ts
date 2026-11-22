import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '../App.vue'
import RepositoryListView from '../views/RepositoryListView.vue'
import RepositoryDetailView from '../views/RepositoryDetailView.vue'
import SettingsView from '../views/SettingsView.vue'

async function mountApp() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: RepositoryListView },
      { path: '/repositories/:id', component: RepositoryDetailView },
      { path: '/settings', component: SettingsView },
    ],
  })
  router.push('/')
  await router.isReady()
  return mount(App, { global: { plugins: [router] } })
}

describe('App', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the radar-dashboard header link', async () => {
    const wrapper = await mountApp()

    expect(wrapper.text()).toContain('radar-dashboard')
  })

  it('navigates to Settings via the header link', async () => {
    const wrapper = await mountApp()

    await wrapper.get('a[href="/settings"]').trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(SettingsView).exists()).toBe(true)
  })

  describe('online build', () => {
    afterEach(() => {
      vi.unstubAllEnvs()
    })

    it('shows the public brand and no link to the local Settings', async () => {
      vi.stubEnv('VITE_RADAR_MODE', 'online')

      const wrapper = await mountApp()

      expect(wrapper.text()).toContain('Engineering-Radar')
      expect(wrapper.find('a[href="/settings"]').exists()).toBe(false)
    })
  })
})
