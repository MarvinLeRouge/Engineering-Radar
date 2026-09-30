import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as client from '@/api/client'
import { useRepositoriesStore } from '../repositories'

vi.mock('@/api/client')

describe('repositories store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchList populates list on success', async () => {
    const repos = [
      { id: 1, name: 'repo', path: '/tmp/repo', global_score: 7, audit_status: 'scored' as const },
    ]
    vi.mocked(client.listRepositories).mockResolvedValueOnce(repos)
    const store = useRepositoriesStore()

    await store.fetchList()

    expect(store.list).toEqual(repos)
    expect(store.listLoading).toBe(false)
    expect(store.listError).toBeNull()
  })

  it('fetchList sets listError and clears loading on failure', async () => {
    vi.mocked(client.listRepositories).mockRejectedValueOnce(new Error('network down'))
    const store = useRepositoriesStore()

    await store.fetchList()

    expect(store.listError).toBe('network down')
    expect(store.listLoading).toBe(false)
    expect(store.list).toEqual([])
  })

  it('fetchReport populates report on success', async () => {
    const report = { repository_id: 1, repository_name: 'repo', commit_sha: 'a', audited_at: '2026-01-01', scored_at: '2026-01-01', categories: [] }
    vi.mocked(client.getRepositoryReport).mockResolvedValueOnce(report)
    const store = useRepositoriesStore()

    await store.fetchReport(1)

    expect(store.report).toEqual(report)
    expect(store.reportError).toBeNull()
  })

  it('fetchReport sets reportError on failure', async () => {
    vi.mocked(client.getRepositoryReport).mockRejectedValueOnce(new Error('not found'))
    const store = useRepositoriesStore()

    await store.fetchReport(999)

    expect(store.reportError).toBe('not found')
    expect(store.report).toBeNull()
  })

  it('fetchRoadmap populates roadmap on success', async () => {
    const items = [
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
    vi.mocked(client.getRepositoryRoadmap).mockResolvedValueOnce(items)
    const store = useRepositoriesStore()

    await store.fetchRoadmap(1)

    expect(store.roadmap).toEqual(items)
    expect(store.roadmapError).toBeNull()
  })

  it('fetchRoadmap sets roadmapError on failure', async () => {
    vi.mocked(client.getRepositoryRoadmap).mockRejectedValueOnce(new Error('boom'))
    const store = useRepositoriesStore()

    await store.fetchRoadmap(1)

    expect(store.roadmapError).toBe('boom')
    expect(store.roadmap).toEqual([])
  })
})
