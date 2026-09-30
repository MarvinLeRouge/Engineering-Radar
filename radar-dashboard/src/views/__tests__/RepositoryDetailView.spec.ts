import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useRepositoriesStore } from '@/stores/repositories'
import RepositoryDetailView from '../RepositoryDetailView.vue'

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/repositories/:id', component: RepositoryDetailView }],
  })
  router.push('/repositories/1')
  await router.isReady()
  const wrapper = mount(RepositoryDetailView, { global: { plugins: [router] } })
  await wrapper.vm.$nextTick()
  await wrapper.vm.$nextTick()
  return wrapper
}

describe('RepositoryDetailView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows the report error state', async () => {
    const store = useRepositoriesStore()
    store.fetchReport = vi.fn<(repositoryId: number) => Promise<void>>(async () => {
      store.reportError = 'no score found for this repository'
    })
    store.fetchRoadmap = vi.fn<(repositoryId: number) => Promise<void>>()

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('no score found for this repository')
  })

  it('renders categories, criteria, and findings from the report', async () => {
    const store = useRepositoriesStore()
    store.fetchReport = vi.fn<(repositoryId: number) => Promise<void>>(async () => {
      store.report = {
        repository_id: 1,
        repository_name: 'repo-a',
        commit_sha: 'a',
        audited_at: '2026-01-01',
        scored_at: '2026-01-01',
        categories: [
          {
            id: 1,
            name: 'Security',
            order: 1,
            status: 'scored',
            value: 5,
            confidence: 'HIGH',
            criteria: [
              {
                id: 1,
                name: 'SAST findings',
                status: 'scored',
                value: 4,
                na_reason: null,
                findings: [
                  {
                    id: 1,
                    severity: 'HIGH',
                    description: 'issue',
                    file: null,
                    line: null,
                    status: 'OPEN',
                    human_verdict: 'UNREVIEWED',
                    recommendation: null,
                  },
                ],
              },
            ],
          },
        ],
      }
    })
    store.fetchRoadmap = vi.fn<(repositoryId: number) => Promise<void>>()

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Security')
    expect(wrapper.text()).toContain('SAST findings')
    expect(wrapper.findComponent({ name: 'FindingCard' }).exists()).toBe(true)
  })

  it('switches to the roadmap tab and renders roadmap items', async () => {
    const store = useRepositoriesStore()
    store.fetchReport = vi.fn<(repositoryId: number) => Promise<void>>()
    store.fetchRoadmap = vi.fn<(repositoryId: number) => Promise<void>>(async () => {
      store.roadmap = [
        {
          id: 1,
          improvement_task_id: 1,
          title: 'Fix it',
          description: '...',
          status: 'TODO',
          priority: 1,
          estimated_effort: null,
          estimated_impact: null,
          promoted_at: '2026-01-01',
          done_at: null,
        },
      ]
    })

    const wrapper = await mountView()
    await wrapper.findAll('button')[1]!.trigger('click')

    expect(wrapper.findComponent({ name: 'RoadmapItemRow' }).exists()).toBe(true)
  })
})
