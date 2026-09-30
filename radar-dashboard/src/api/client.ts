import { useApiKeyStore } from '@/stores/apiKey'

export class ApiError extends Error {
  status: number

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
  }
}

export interface RepositoryRead {
  id: number
  name: string
  path: string
  global_score: number | null
  audit_status: 'scored' | 'not_yet_audited'
}

export interface FindingReport {
  id: number
  severity: string
  description: string
  file: string | null
  line: number | null
  status: string
  human_verdict: string
  recommendation: string | null
}

export interface CriterionReport {
  id: number
  name: string
  status: 'scored' | 'not_applicable' | 'not_yet_audited'
  value: number | null
  na_reason: string | null
  findings: FindingReport[]
}

export interface CategoryReport {
  id: number
  name: string
  order: number
  status: 'scored' | 'not_yet_audited'
  value: number | null
  confidence: string | null
  criteria: CriterionReport[]
}

export interface RepositoryReport {
  repository_id: number
  repository_name: string
  commit_sha: string
  audited_at: string
  scored_at: string
  categories: CategoryReport[]
}

export interface RoadmapItemRead {
  id: number
  improvement_task_id: number
  title: string
  description: string
  status: string
  priority: number
  estimated_effort: string | null
  estimated_impact: string | null
  promoted_at: string
  done_at: string | null
}

export interface EvidenceCandidate {
  id: number
  finding_id: number
  evidence_type: string
  content: string
  created_at: string
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, init)

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') {
        detail = body.detail
      }
    } catch {
      // response body was not JSON; keep statusText
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

function writeHeaders(): HeadersInit {
  const apiKeyStore = useApiKeyStore()
  return {
    'Content-Type': 'application/json',
    'X-API-Key': apiKeyStore.apiKey,
  }
}

export function listRepositories(): Promise<RepositoryRead[]> {
  return request<RepositoryRead[]>('/repositories')
}

export function getRepositoryReport(repositoryId: number): Promise<RepositoryReport> {
  return request<RepositoryReport>(`/repositories/${repositoryId}/report`)
}

export function getRepositoryRoadmap(repositoryId: number): Promise<RoadmapItemRead[]> {
  return request<RoadmapItemRead[]>(`/repositories/${repositoryId}/roadmap`)
}

export function getRoadmapItemEvidenceCandidates(
  roadmapItemId: number,
): Promise<EvidenceCandidate[]> {
  return request<EvidenceCandidate[]>(`/roadmap-items/${roadmapItemId}/evidence-candidates`)
}

export function updateFindingVerdict(findingId: number, humanVerdict: string): Promise<void> {
  return request<void>(`/findings/${findingId}/verdict`, {
    method: 'PATCH',
    headers: writeHeaders(),
    body: JSON.stringify({ human_verdict: humanVerdict }),
  })
}

export function updateFindingStatus(findingId: number, status: string): Promise<void> {
  return request<void>(`/findings/${findingId}/status`, {
    method: 'PATCH',
    headers: writeHeaders(),
    body: JSON.stringify({ status }),
  })
}

export function updateRoadmapItemStatus(
  roadmapItemId: number,
  status: string,
  doneEvidenceId?: number,
): Promise<void> {
  const body: Record<string, unknown> = { status }
  if (doneEvidenceId !== undefined) {
    body.done_evidence_id = doneEvidenceId
  }
  return request<void>(`/roadmap-items/${roadmapItemId}/status`, {
    method: 'PATCH',
    headers: writeHeaders(),
    body: JSON.stringify(body),
  })
}
