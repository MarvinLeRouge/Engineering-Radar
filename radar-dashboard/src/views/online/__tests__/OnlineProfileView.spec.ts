import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import * as online from '@/api/online'
import { ApiError } from '@/api/client'
import type { Profile } from '@/api/online'
import OnlineProfileView from '../OnlineProfileView.vue'

vi.mock('@/api/online', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/online')>()
  return { ...actual, getProfile: vi.fn<(user: string) => Promise<Profile>>() }
})

async function mountView(path = '/u/ada') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/u/:user', component: OnlineProfileView },
      { path: '/u/:user/:repo', component: { template: '<div />' } },
    ],
  })
  router.push(path)
  await router.isReady()
  const wrapper = mount(OnlineProfileView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('OnlineProfileView', () => {
  beforeEach(() => {
    vi.mocked(online.getProfile).mockReset()
  })

  it('lists the published repositories with their latest score', async () => {
    vi.mocked(online.getProfile).mockResolvedValue({
      slug: 'ada',
      display_name: 'Ada',
      repositories: [
        {
          slug: 'summit-stats',
          display_name: 'Summit-Stats',
          latest_global_score: 8.1,
          latest_scored_at: '2026-11-10T10:00:00Z',
        },
        {
          slug: 'empty',
          display_name: 'Empty',
          latest_global_score: null,
          latest_scored_at: null,
        },
      ],
    })

    const wrapper = await mountView()

    expect(online.getProfile).toHaveBeenCalledWith('ada')
    expect(wrapper.find('h1').text()).toBe('Ada')
    const link = wrapper.find('a[href="/u/ada/summit-stats"]')
    expect(link.text()).toBe('Summit-Stats')
    expect(wrapper.findAll('.score-gauge').map((gauge) => gauge.text())).toEqual(['8.1', '-'])
  })

  it('says when nothing is published yet', async () => {
    vi.mocked(online.getProfile).mockResolvedValue({
      slug: 'ada',
      display_name: 'Ada',
      repositories: [],
    })

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('No repository published yet.')
  })

  it('shows a not-found state for an unknown user', async () => {
    vi.mocked(online.getProfile).mockRejectedValue(new ApiError(404, 'user not found'))

    const wrapper = await mountView('/u/nobody')

    expect(wrapper.text()).toContain('No published profile here.')
  })

  it('shows other errors as they are', async () => {
    vi.mocked(online.getProfile).mockRejectedValue(new ApiError(500, 'Internal Server Error'))

    const wrapper = await mountView()

    expect(wrapper.find('[role="alert"]').text()).toContain('Internal Server Error')
  })
})
