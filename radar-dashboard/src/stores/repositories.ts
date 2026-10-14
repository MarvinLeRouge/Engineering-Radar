import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as client from '@/api/client'
import type {
  RepositoryRead,
  RepositoryReport,
  RoadmapItemRead,
  ScoreHistoryPoint,
} from '@/api/client'

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'unexpected error'
}

export const useRepositoriesStore = defineStore('repositories', () => {
  const list = ref<RepositoryRead[]>([])
  const listLoading = ref(false)
  const listError = ref<string | null>(null)

  const report = ref<RepositoryReport | null>(null)
  const reportLoading = ref(false)
  const reportError = ref<string | null>(null)

  const roadmap = ref<RoadmapItemRead[]>([])
  const roadmapLoading = ref(false)
  const roadmapError = ref<string | null>(null)

  const scoreHistory = ref<ScoreHistoryPoint[]>([])
  const scoreHistoryLoading = ref(false)
  const scoreHistoryError = ref<string | null>(null)

  async function fetchList(): Promise<void> {
    listLoading.value = true
    listError.value = null
    try {
      list.value = await client.listRepositories()
    } catch (error) {
      listError.value = errorMessage(error)
    } finally {
      listLoading.value = false
    }
  }

  async function fetchReport(repositoryId: number, scoringRunId?: number): Promise<void> {
    reportLoading.value = true
    reportError.value = null
    try {
      report.value = await client.getRepositoryReport(repositoryId, scoringRunId)
    } catch (error) {
      reportError.value = errorMessage(error)
    } finally {
      reportLoading.value = false
    }
  }

  async function fetchScoreHistory(repositoryId: number): Promise<void> {
    scoreHistoryLoading.value = true
    scoreHistoryError.value = null
    try {
      scoreHistory.value = await client.getScoreHistory(repositoryId)
    } catch (error) {
      scoreHistoryError.value = errorMessage(error)
    } finally {
      scoreHistoryLoading.value = false
    }
  }

  async function fetchRoadmap(repositoryId: number): Promise<void> {
    roadmapLoading.value = true
    roadmapError.value = null
    try {
      roadmap.value = await client.getRepositoryRoadmap(repositoryId)
    } catch (error) {
      roadmapError.value = errorMessage(error)
    } finally {
      roadmapLoading.value = false
    }
  }

  return {
    list,
    listLoading,
    listError,
    fetchList,
    report,
    reportLoading,
    reportError,
    fetchReport,
    roadmap,
    roadmapLoading,
    roadmapError,
    fetchRoadmap,
    scoreHistory,
    scoreHistoryLoading,
    scoreHistoryError,
    fetchScoreHistory,
  }
})
