<!-- radar-dashboard/src/views/online/OnlineReportView.vue -->
<template>
  <div class="online-report">
    <nav class="online-report__tabs">
      <button
        type="button"
        data-testid="tab-report"
        :class="{ active: tab === 'report' }"
        @click="tab = 'report'"
      >
        Report
      </button>
      <button
        type="button"
        data-testid="tab-trends"
        :class="{ active: tab === 'trends' }"
        @click="showTrends"
      >
        Trends
      </button>
    </nav>

    <p v-if="loading" class="online-report__status" role="status">Loading...</p>
    <p v-else-if="notFound" class="online-report__status">Nothing published here.</p>
    <p v-else-if="error" class="online-report__error" role="alert">{{ error }}</p>

    <section v-else-if="published && shown && tab === 'report'">
      <RouterLink :to="`/u/${published.user.slug}`" class="online-report__owner">{{
        published.user.display_name
      }}</RouterLink>
      <h1 class="page-title online-report__title">
        <span>{{ published.repository.display_name }}</span>
        <ScoreGauge
          class="online-report__global-score"
          :value="shown.global_score"
          :status="shown.global_score === null ? 'not_yet_audited' : 'scored'"
        />
      </h1>
      <p class="online-report__meta">
        <!-- One span: the flex gap would otherwise split "abc1234," from its comma. -->
        <span
          >Commit <code :title="shown.commit_sha">{{ shown.commit_sha.slice(0, 7) }}</code
          >, scored on {{ formatDate(shown.scored_at) }}</span
        >
        <span v-if="selectedIndex === null">(latest)</span>
        <button
          v-else
          type="button"
          class="online-report__latest"
          data-testid="show-latest"
          @click="selectedIndex = null"
        >
          Show latest
        </button>
        <span class="online-report__methodology">{{ published.report.methodology_version }}</span>
      </p>
      <p class="online-report__note">
        Self-assessed: computed by the owner's own Engineering-Radar, not independently verified.
        Only global and category scores are published.
      </p>
      <ul class="online-report__categories">
        <li v-for="category in shown.categories" :key="category.name">
          <span class="online-report__category-name">{{ category.name }}</span>
          <ScoreGauge
            v-if="category.implemented"
            :value="category.value"
            :status="category.value === null ? 'not_yet_audited' : 'scored'"
          />
          <span v-else class="online-report__not-implemented">Not implemented yet</span>
        </li>
      </ul>
    </section>

    <section v-else-if="published && tab === 'trends'">
      <p v-if="historyLoading" class="online-report__status" role="status">Loading...</p>
      <p v-else-if="historyError" class="online-report__error" role="alert">
        {{ historyError }}
      </p>
      <ScoreHistoryChart v-else :points="chartPoints" @select-point="showCommit" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import ScoreGauge from '@/components/ScoreGauge.vue'
import ScoreHistoryChart from '@/components/ScoreHistoryChart.vue'
import { ApiError } from '@/api/client'
import {
  getPublicHistory,
  getPublicReport,
  toScoreHistoryPoints,
  type PublicHistoryCategory,
  type PublicHistoryPoint,
  type PublicReport,
} from '@/api/online'

interface ShownScores {
  commit_sha: string
  scored_at: string
  global_score: number | null
  categories: PublicHistoryCategory[]
}

const route = useRoute()
const user = route.params.user as string
const repository = route.params.repo as string

const tab = ref<'report' | 'trends'>('report')
const published = ref<PublicReport | null>(null)
const loading = ref(true)
const notFound = ref(false)
const error = ref<string | null>(null)

const history = ref<PublicHistoryPoint[] | null>(null)
const historyLoading = ref(false)
const historyError = ref<string | null>(null)
/** Index in `history` of the commit picked in the chart; null shows the latest report. */
const selectedIndex = ref<number | null>(null)

const chartPoints = computed(() => toScoreHistoryPoints(history.value ?? []))

const shown = computed<ShownScores | null>(() => {
  const picked = selectedIndex.value === null ? undefined : history.value?.[selectedIndex.value]
  if (picked) return picked
  const latest = published.value?.report
  return latest ?? null
})

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString()
}

function messageOf(caught: unknown): string {
  return caught instanceof Error ? caught.message : 'unexpected error'
}

async function showTrends(): Promise<void> {
  tab.value = 'trends'
  if (history.value !== null || historyLoading.value) return
  historyLoading.value = true
  historyError.value = null
  try {
    history.value = await getPublicHistory(user, repository)
  } catch (caught) {
    historyError.value = messageOf(caught)
  } finally {
    historyLoading.value = false
  }
}

function showCommit(index: number): void {
  selectedIndex.value = index
  tab.value = 'report'
}

onMounted(async () => {
  try {
    published.value = await getPublicReport(user, repository)
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) {
      notFound.value = true
    } else {
      error.value = messageOf(caught)
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.online-report__tabs {
  display: flex;
  gap: var(--space-5);
  margin-bottom: var(--space-6);
  border-bottom: 1px solid var(--color-border);
}

.online-report__tabs button {
  appearance: none;
  background: none;
  border: none;
  padding: var(--space-3) var(--space-1);
  margin-bottom: -1px;
  font-size: var(--text-body);
  font-weight: var(--weight-medium);
  color: var(--color-ink-soft);
  border-bottom: 2px solid transparent;
  cursor: pointer;
}

.online-report__tabs button.active {
  color: var(--color-ink);
  font-weight: var(--weight-semibold);
  border-bottom-color: var(--color-accent);
}

.online-report__status {
  color: var(--color-ink-soft);
}

.online-report__error {
  color: var(--text-danger);
  font-weight: var(--weight-medium);
}

.online-report__owner {
  display: inline-block;
  font-size: var(--text-meta);
  font-weight: var(--weight-medium);
  margin-bottom: var(--space-1);
}

.online-report__title {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.online-report__global-score {
  min-width: 4rem;
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-subtitle);
}

.online-report__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
  margin-bottom: var(--space-4);
}

.online-report__meta code {
  font-family: var(--font-mono);
  color: var(--color-ink);
}

.online-report__methodology::before {
  content: '·';
  margin-right: var(--space-2);
}

.online-report__latest {
  appearance: none;
  background: none;
  border: none;
  padding: 0;
  font-size: inherit;
  font-weight: var(--weight-medium);
  color: var(--color-accent);
  cursor: pointer;
}

.online-report__latest:hover {
  text-decoration: underline;
}

.online-report__note {
  max-width: 40rem;
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-6);
  border-radius: var(--radius-md);
  background: var(--color-surface-sunken);
  font-size: var(--text-meta);
  line-height: var(--leading-normal);
  color: var(--color-ink-soft);
}

.online-report__categories {
  list-style: none;
  padding: 0;
  border-top: 1px solid var(--color-border);
}

.online-report__categories li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-1);
  border-bottom: 1px solid var(--color-border);
}

.online-report__category-name {
  font-size: var(--text-subtitle);
  font-weight: var(--weight-medium);
}

.online-report__not-implemented {
  padding: var(--space-1) var(--space-2);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-size: var(--text-meta);
  font-weight: var(--weight-medium);
  color: var(--color-ink-faint);
  white-space: nowrap;
}
</style>
