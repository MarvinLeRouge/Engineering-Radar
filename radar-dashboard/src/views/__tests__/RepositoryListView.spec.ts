import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useRepositoriesStore } from '@/stores/repositories'
import RepositoryListView from '../RepositoryListView.vue'

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: RepositoryListView },
      { path: '/repositories/:idSlug', component: { template: '<div />' } },
    ],
  })
  router.push('/')
  await router.isReady()
  return mount(RepositoryListView, { global: { plugins: [router] } })
}

describe('RepositoryListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows a loading state while the list is in flight', async () => {
    const store = useRepositoriesStore()
    store.fetchList = vi.fn<() => Promise<void>>().mockReturnValue(new Promise(() => {}))

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Loading')
  })

  it('shows the error state when listError is set', async () => {
    const store = useRepositoriesStore()
    store.fetchList = vi.fn<() => Promise<void>>(async () => {
      store.listError = 'failed to load repositories'
    })

    const wrapper = await mountView()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('failed to load repositories')
  })

  it('renders each repository with a link and a gauge', async () => {
    const store = useRepositoriesStore()
    store.fetchList = vi.fn<() => Promise<void>>(async () => {
      store.list = [
        { id: 1, name: 'repo-a', path: '/tmp/repo-a', global_score: 7.5, audit_status: 'scored' },
      ]
    })

    const wrapper = await mountView()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('repo-a')
    expect(wrapper.findComponent({ name: 'ScoreGauge' }).exists()).toBe(true)
    expect(wrapper.find('a').attributes('href')).toBe('/repositories/repo-a-1')
  })
})
