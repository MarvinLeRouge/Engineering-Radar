import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  getProfile,
  getPublicHistory,
  getPublicReport,
  toScoreHistoryPoints,
  type PublicHistoryPoint,
} from '../online'

function mockFetch(body: unknown, status = 200) {
  const fetchMock = vi.fn<typeof fetch>(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('online API client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('reads the public endpoints under /api/users without any API key', async () => {
    const fetchMock = mockFetch({})

    await getProfile('ada')
    await getPublicReport('ada', 'summit-stats')
    await getPublicHistory('ada', 'summit-stats')

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/users/ada',
      '/api/users/ada/repositories/summit-stats/report',
      '/api/users/ada/repositories/summit-stats/history',
    ])
    for (const [, init] of fetchMock.mock.calls) {
      expect(JSON.stringify(init ?? {})).not.toContain('X-API-Key')
    }
  })

  it('encodes path segments', async () => {
    const fetchMock = mockFetch({})

    await getProfile('a/b')

    expect(fetchMock.mock.calls[0]![0]).toBe('/api/users/a%2Fb')
  })
})

describe('toScoreHistoryPoints', () => {
  const history: PublicHistoryPoint[] = [
    {
      commit_sha: 'a'.repeat(40),
      scored_at: '2026-11-05T10:00:00Z',
      global_score: 7.4,
      categories: [
        { name: 'Security', order: 4, value: 7.4, implemented: true },
        { name: 'Performance', order: 6, value: null, implemented: false },
      ],
    },
    {
      commit_sha: 'b'.repeat(40),
      scored_at: '2026-11-10T10:00:00Z',
      global_score: 8.1,
      categories: [{ name: 'Security', order: 4, value: 8.1, implemented: true }],
    },
  ]

  it('feeds the shared chart: categories keyed by order, points keyed by position', () => {
    const points = toScoreHistoryPoints(history)

    expect(points.map((point) => point.scoring_run_id)).toEqual([0, 1])
    expect(points[0]!.categories).toEqual([
      { id: 4, name: 'Security', value: 7.4, implemented: true },
      { id: 6, name: 'Performance', value: null, implemented: false },
    ])
    expect(points[1]!.global_score).toBe(8.1)
    expect(points[1]!.commit_sha).toBe('b'.repeat(40))
    expect(points.every((point) => point.risk.length === 0 && point.risk_index === 0)).toBe(true)
  })
})
