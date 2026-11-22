import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import * as online from '@/api/online'
import { ApiError } from '@/api/client'
import type { PublicHistoryPoint, PublicReport } from '@/api/online'
import OnlineReportView from '../OnlineReportView.vue'

// See ScoreHistoryChart.spec.ts: jsdom has no <canvas> 2D context.
vi.mock('vue-chartjs', () => ({
  Line: { name: 'LineStub', props: ['data', 'options'], template: '<div />' },
}))

vi.mock('@/api/online', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/online')>()
  return {
    ...actual,
    getPublicReport: vi.fn<(user: string, repository: string) => Promise<PublicReport>>(),
    getPublicHistory: vi.fn<(user: string, repository: string) => Promise<PublicHistoryPoint[]>>(),
  }
})

const report: PublicReport = {
  user: { slug: 'ada', display_name: 'Ada' },
  repository: { slug: 'summit-stats', display_name: 'Summit-Stats' },
  uploaded_at: '2026-11-10T11:00:00Z',
  report: {
    schema_version: 1,
    repository: { slug: 'summit-stats', display_name: 'Summit-Stats' },
    commit_sha: 'b'.repeat(40),
    scored_at: '2026-11-10T10:00:00Z',
    methodology_version: 'Quality Framework v1.0',
    global_score: 8.1,
    categories: [
      {
        name: 'Security',
        order: 4,
        weight: 1.5,
        status: 'scored',
        implemented: true,
        value: 8.1,
        confidence: 'HIGH',
      },
      {
        name: 'Performance',
        order: 6,
        weight: 1,
        status: 'not_yet_audited',
        implemented: false,
        value: null,
        confidence: null,
      },
    ],
  },
}

const history: PublicHistoryPoint[] = [
  {
    commit_sha: 'a'.repeat(40),
    scored_at: '2026-11-05T10:00:00Z',
    global_score: 6.3,
    categories: [
      { name: 'Security', order: 4, value: 6.3, implemented: true },
      { name: 'Performance', order: 6, value: null, implemented: false },
    ],
  },
  {
    commit_sha: 'b'.repeat(40),
    scored_at: '2026-11-10T10:00:00Z',
    global_score: 8.1,
    categories: [
      { name: 'Security', order: 4, value: 8.1, implemented: true },
      { name: 'Performance', order: 6, value: null, implemented: false },
    ],
  },
]

async function mountView(path = '/u/ada/summit-stats') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/u/:user', component: { template: '<div />' } },
      { path: '/u/:user/:repo', component: OnlineReportView },
    ],
  })
  router.push(path)
  await router.isReady()
  const wrapper = mount(OnlineReportView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('OnlineReportView', () => {
  beforeEach(() => {
    vi.mocked(online.getPublicReport).mockReset().mockResolvedValue(report)
    vi.mocked(online.getPublicHistory).mockReset().mockResolvedValue(history)
  })

  it('shows the latest published scores, marked self-assessed', async () => {
    const wrapper = await mountView()

    expect(online.getPublicReport).toHaveBeenCalledWith('ada', 'summit-stats')
    const title = wrapper.find('h1')
    expect(title.text()).toContain('Summit-Stats')
    expect(title.find('.score-gauge').text()).toBe('8.1')
    const text = wrapper.text()
    expect(text).toContain('Ada')
    expect(text).toContain('bbbbbbb')
    expect(text).toContain('Quality Framework v1.0')
    expect(text).toContain('Self-assessed')
    expect(text).toContain('Security')
    expect(text).toContain('Not implemented yet')
    expect(wrapper.find('a[href="/u/ada"]').exists()).toBe(true)
  })

  it('never shows local-only controls', async () => {
    const wrapper = await mountView()

    const text = wrapper.text()
    for (const local of ['Roadmap', 'Settings', 'Publish', 'Weighted risk', 'HIGH']) {
      expect(text).not.toContain(local)
    }
    expect(wrapper.findAll('select')).toHaveLength(0)
  })

  it('loads the history when the trends tab opens', async () => {
    const wrapper = await mountView()

    await wrapper.find('[data-testid="tab-trends"]').trigger('click')
    await flushPromises()

    expect(online.getPublicHistory).toHaveBeenCalledWith('ada', 'summit-stats')
    const chart = wrapper.findComponent({ name: 'ScoreHistoryChart' })
    expect(chart.props('points')).toHaveLength(2)
  })

  it('shows the scores of a commit picked in the trends chart, with a way back', async () => {
    const wrapper = await mountView()
    await wrapper.find('[data-testid="tab-trends"]').trigger('click')
    await flushPromises()

    await wrapper.findComponent({ name: 'ScoreHistoryChart' }).vm.$emit('select-point', 0)
    await flushPromises()

    expect(wrapper.find('h1 .score-gauge').text()).toBe('6.3')
    expect(wrapper.text()).toContain('aaaaaaa')
    expect(wrapper.text()).not.toContain('(latest)')

    await wrapper.find('[data-testid="show-latest"]').trigger('click')

    expect(wrapper.find('h1 .score-gauge').text()).toBe('8.1')
    expect(wrapper.text()).toContain('(latest)')
  })

  it('shows a not-found state for an unknown repository', async () => {
    vi.mocked(online.getPublicReport).mockRejectedValue(new ApiError(404, 'repository not found'))

    const wrapper = await mountView('/u/ada/other')

    expect(wrapper.text()).toContain('Nothing published here.')
  })

  it('shows other errors as they are', async () => {
    vi.mocked(online.getPublicReport).mockRejectedValue(new ApiError(500, 'Internal Server Error'))

    const wrapper = await mountView()

    expect(wrapper.find('[role="alert"]').text()).toContain('Internal Server Error')
  })
})
