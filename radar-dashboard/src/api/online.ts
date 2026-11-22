// Read-only client of the public radar-online API (online build only): no API key,
// nothing beyond what an account holder chose to publish.
import { request } from './client'
import type { PublicationPayload, ScoreHistoryPoint } from './client'

export interface PublicName {
  slug: string
  display_name: string
}

export interface RepositorySummary extends PublicName {
  latest_global_score: number | null
  latest_scored_at: string | null
}

export interface Profile extends PublicName {
  repositories: RepositorySummary[]
}

export interface PublicReport {
  user: PublicName
  repository: PublicName
  uploaded_at: string
  report: PublicationPayload
}

export interface PublicHistoryCategory {
  name: string
  order: number
  value: number | null
  implemented: boolean
}

export interface PublicHistoryPoint {
  commit_sha: string
  scored_at: string
  global_score: number | null
  categories: PublicHistoryCategory[]
}

function userPath(user: string): string {
  return `/users/${encodeURIComponent(user)}`
}

function repositoryPath(user: string, repository: string): string {
  return `${userPath(user)}/repositories/${encodeURIComponent(repository)}`
}

export function getProfile(user: string): Promise<Profile> {
  return request<Profile>(userPath(user))
}

export function getPublicReport(user: string, repository: string): Promise<PublicReport> {
  return request<PublicReport>(`${repositoryPath(user, repository)}/report`)
}

export function getPublicHistory(user: string, repository: string): Promise<PublicHistoryPoint[]> {
  return request<PublicHistoryPoint[]>(`${repositoryPath(user, repository)}/history`)
}

/**
 * Shape the public history for the shared ScoreHistoryChart: a category is keyed by its
 * taxonomy order (unique within a methodology version) and a point by its position, which
 * is what the chart's select-point event then reports. No risk is ever published.
 */
export function toScoreHistoryPoints(history: PublicHistoryPoint[]): ScoreHistoryPoint[] {
  return history.map((point, index) => ({
    scoring_run_id: index,
    audit_id: index,
    commit_sha: point.commit_sha,
    scored_at: point.scored_at,
    global_score: point.global_score,
    categories: point.categories.map((category) => ({
      id: category.order,
      name: category.name,
      value: category.value,
      implemented: category.implemented,
    })),
    risk: [],
    risk_index: 0,
  }))
}
