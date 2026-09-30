import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useApiKeyStore } from '@/stores/apiKey'
import {
  ApiError,
  getRepositoryReport,
  getRoadmapItemEvidenceCandidates,
  listRepositories,
  updateFindingStatus,
  updateFindingVerdict,
  updateRoadmapItemStatus,
} from '../client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api/client', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('fetch', vi.fn())
  })

  it('listRepositories calls GET /api/repositories and returns the parsed body', async () => {
    const repos = [
      { id: 1, name: 'repo', path: '/tmp/repo', global_score: null, audit_status: 'not_yet_audited' },
    ]
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(repos))

    const result = await listRepositories()

    expect(fetch).toHaveBeenCalledWith('/api/repositories', {})
    expect(result).toEqual(repos)
  })

  it('getRepositoryReport calls GET /api/repositories/:id/report', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ repository_id: 1, categories: [] }))

    await getRepositoryReport(1)

    expect(fetch).toHaveBeenCalledWith('/api/repositories/1/report', {})
  })

  it('getRoadmapItemEvidenceCandidates calls GET /api/roadmap-items/:id/evidence-candidates', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse([]))

    await getRoadmapItemEvidenceCandidates(7)

    expect(fetch).toHaveBeenCalledWith('/api/roadmap-items/7/evidence-candidates', {})
  })

  it('throws an ApiError carrying the status and server detail on a non-ok response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ detail: 'not found' }, 404))

    await expect(getRepositoryReport(999)).rejects.toMatchObject({
      status: 404,
      message: 'not found',
    })
  })

  it('falls back to statusText when the error body is not JSON', async () => {
    const response = new Response('plain text', { status: 500, statusText: 'Server Error' })
    vi.mocked(fetch).mockResolvedValueOnce(response)

    await expect(getRepositoryReport(1)).rejects.toMatchObject({
      status: 500,
      message: 'Server Error',
    })
  })

  it('sends the X-API-Key header from the apiKey store on a write call', async () => {
    useApiKeyStore().setApiKey('secret')
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}))

    await updateFindingStatus(1, 'RESOLVED')

    const [url, init] = vi.mocked(fetch).mock.calls[0]!
    expect(url).toBe('/api/findings/1/status')
    expect((init?.headers as Record<string, string>)['X-API-Key']).toBe('secret')
    expect(JSON.parse(init?.body as string)).toEqual({ status: 'RESOLVED' })
  })

  it('sends human_verdict as the body for updateFindingVerdict', async () => {
    useApiKeyStore().setApiKey('secret')
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}))

    await updateFindingVerdict(1, 'TRUE_POSITIVE')

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    expect(JSON.parse(init?.body as string)).toEqual({ human_verdict: 'TRUE_POSITIVE' })
  })

  it('omits done_evidence_id entirely for a non-DONE roadmap status update', async () => {
    useApiKeyStore().setApiKey('secret')
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}))

    await updateRoadmapItemStatus(1, 'IN_PROGRESS')

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    const body = JSON.parse(init?.body as string) as Record<string, unknown>
    expect('done_evidence_id' in body).toBe(false)
  })

  it('includes done_evidence_id for a DONE roadmap status update', async () => {
    useApiKeyStore().setApiKey('secret')
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}))

    await updateRoadmapItemStatus(1, 'DONE', 42)

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    const body = JSON.parse(init?.body as string) as Record<string, unknown>
    expect(body.done_evidence_id).toBe(42)
  })

  it('ApiError is an instance of Error', () => {
    const error = new ApiError(401, 'invalid or missing API key')

    expect(error).toBeInstanceOf(Error)
    expect(error.status).toBe(401)
    expect(error.message).toBe('invalid or missing API key')
  })
})
