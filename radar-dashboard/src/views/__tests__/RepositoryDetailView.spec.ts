import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useRepositoriesStore } from '@/stores/repositories'
import RepositoryDetailView from '../RepositoryDetailView.vue'
import type { RoadmapItemRead } from '@/api/client'

async function mountView(path = '/repositories/repo-a-1') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/repositories/:idSlug', component: RepositoryDetailView }],
  })
  router.push(path)
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

  it('shows a not-found state when the route slug has no trailing numeric id', async () => {
    const store = useRepositoriesStore()
    store.fetchReport = vi.fn<(repositoryId: number) => Promise<void>>()
    store.fetchRoadmap = vi.fn<(repositoryId: number) => Promise<void>>()

    const wrapper = await mountView('/repositories/not-a-valid-slug')

    expect(wrapper.text()).toContain('repository not found')
    expect(store.fetchReport).not.toHaveBeenCalled()
    expect(store.fetchRoadmap).not.toHaveBeenCalled()
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
    expect(wrapper.text()).toContain('HIGH (1)')
    expect(wrapper.findComponent({ name: 'FindingCard' }).exists()).toBe(false)

    await wrapper.find('[data-testid="severity-chip"]').trigger('click')

    expect(wrapper.findComponent({ name: 'FindingCard' }).exists()).toBe(true)
  })

  it('keeps existing report content visible during a refetch instead of flashing Loading', async () => {
    const store = useRepositoriesStore()
    const reportFixture = {
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
          status: 'scored' as const,
          value: 5,
          confidence: 'HIGH' as const,
          criteria: [
            {
              id: 1,
              name: 'SAST findings',
              status: 'scored' as const,
              value: 4,
              na_reason: null,
              findings: [
                {
                  id: 1,
                  severity: 'HIGH' as const,
                  description: 'issue',
                  file: null,
                  line: null,
                  status: 'OPEN' as const,
                  human_verdict: 'UNREVIEWED' as const,
                  recommendation: null,
                },
              ],
            },
          ],
        },
      ],
    }
    let fetchCount = 0
    store.fetchReport = vi.fn<(repositoryId: number) => Promise<void>>(async () => {
      fetchCount += 1
      if (fetchCount === 1) {
        store.report = reportFixture
      } else {
        store.reportLoading = true
      }
    })
    store.fetchRoadmap = vi.fn<(repositoryId: number) => Promise<void>>()

    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Security')

    await wrapper.find('[data-testid="severity-chip"]').trigger('click')
    await wrapper.findComponent({ name: 'FindingCard' }).vm.$emit('updated')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Security')
    expect(wrapper.text()).not.toContain('Loading...')
  })

  it('keeps existing roadmap content visible during a refetch instead of flashing Loading', async () => {
    const store = useRepositoriesStore()
    const roadmapFixture: RoadmapItemRead[] = [
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
    let fetchCount = 0
    store.fetchReport = vi.fn<(repositoryId: number) => Promise<void>>()
    store.fetchRoadmap = vi.fn<(repositoryId: number) => Promise<void>>(async () => {
      fetchCount += 1
      if (fetchCount === 1) {
        store.roadmap = roadmapFixture
      } else {
        store.roadmapLoading = true
      }
    })

    const wrapper = await mountView()
    await wrapper.findAll('button')[1]!.trigger('click')
    expect(wrapper.text()).toContain('Fix it')

    await wrapper.findComponent({ name: 'RoadmapItemRow' }).vm.$emit('updated')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Fix it')
    expect(wrapper.text()).not.toContain('Loading...')
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
