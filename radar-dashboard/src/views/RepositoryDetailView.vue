<!-- radar-dashboard/src/views/RepositoryDetailView.vue -->
<template>
  <div class="repository-detail-view">
    <nav class="repository-detail-view__tabs">
      <button type="button" :class="{ active: tab === 'report' }" @click="tab = 'report'">
        Report
      </button>
      <button type="button" :class="{ active: tab === 'roadmap' }" @click="tab = 'roadmap'">
        Roadmap
      </button>
    </nav>

    <p v-if="repositoryId === null" class="repository-detail-view__error">
      repository not found
    </p>
    <section v-else-if="tab === 'report'">
      <p v-if="store.reportLoading && !store.report" class="repository-detail-view__status">
        Loading...
      </p>
      <p v-else-if="store.reportError" class="repository-detail-view__error">
        {{ store.reportError }}
      </p>
      <template v-else-if="store.report">
        <h1 class="repository-detail-view__title">{{ store.report.repository_name }}</h1>
        <div
          v-for="category in store.report.categories"
          :key="category.id"
          class="category"
        >
          <h2 class="category__heading">
            <span class="category__name">{{ category.name }}</span>
            <ScoreGauge :value="category.value" :status="category.status" />
          </h2>
          <div v-for="criterion in category.criteria" :key="criterion.id" class="criterion">
            <h3 class="criterion__heading">
              <span class="criterion__name">{{ criterion.name }}</span>
              <ScoreGauge
                :value="criterion.value"
                :status="criterion.status"
                :na-reason="criterion.na_reason"
              />
            </h3>
            <CriterionFindings :findings="criterion.findings" @updated="refetchReport" />
          </div>
        </div>
      </template>
    </section>

    <section v-else>
      <p v-if="store.roadmapLoading && !store.roadmap.length" class="repository-detail-view__status">
        Loading...
      </p>
      <p v-else-if="store.roadmapError" class="repository-detail-view__error">
        {{ store.roadmapError }}
      </p>
      <p v-else-if="store.roadmap.length === 0" class="repository-detail-view__status">
        No roadmap items yet.
      </p>
      <ul v-else class="repository-detail-view__roadmap-list">
        <RoadmapItemRow
          v-for="item in store.roadmap"
          :key="item.id"
          :item="item"
          @updated="refetchRoadmap"
        />
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import ScoreGauge from '@/components/ScoreGauge.vue'
import CriterionFindings from '@/components/CriterionFindings.vue'
import RoadmapItemRow from '@/components/RoadmapItemRow.vue'
import { useRepositoriesStore } from '@/stores/repositories'
import { extractRepositoryId } from '@/utils/slugify'

const route = useRoute()
const store = useRepositoriesStore()
const tab = ref<'report' | 'roadmap'>('report')

const repositoryId = extractRepositoryId(route.params.idSlug as string)

function refetchReport(): void {
  if (repositoryId !== null) {
    store.fetchReport(repositoryId)
  }
}

function refetchRoadmap(): void {
  if (repositoryId !== null) {
    store.fetchRoadmap(repositoryId)
  }
}

onMounted(() => {
  refetchReport()
  refetchRoadmap()
})
</script>

<style scoped>
.repository-detail-view__tabs {
  display: flex;
  gap: var(--space-5);
  margin-bottom: var(--space-6);
  border-bottom: 1px solid var(--color-border);
}

.repository-detail-view__tabs button {
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

.repository-detail-view__tabs button.active {
  color: var(--color-ink);
  font-weight: var(--weight-semibold);
  border-bottom-color: var(--color-accent);
}

.repository-detail-view__status {
  color: var(--color-ink-soft);
}

.repository-detail-view__error {
  color: var(--text-danger);
  font-weight: var(--weight-medium);
}

.repository-detail-view__title {
  font-size: var(--text-display);
  font-weight: var(--weight-bold);
  line-height: var(--leading-tight);
  letter-spacing: -0.01em;
  margin-bottom: var(--space-6);
}

.category {
  margin-top: var(--space-7);
}

.category:first-of-type {
  margin-top: 0;
}

.category__heading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-title);
  font-weight: var(--weight-semibold);
  line-height: var(--leading-tight);
  padding-bottom: var(--space-2);
  margin-bottom: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.category__name {
  flex: 1;
}

.criterion {
  margin-left: var(--space-5);
  padding-left: var(--space-4);
  margin-top: var(--space-5);
  border-left: 1px solid var(--color-border);
}

.criterion:first-of-type {
  margin-top: 0;
}

.criterion__heading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-subtitle);
  font-weight: var(--weight-medium);
  color: var(--color-ink-soft);
  margin-bottom: var(--space-3);
}

.criterion__name {
  flex: 1;
}

.repository-detail-view__roadmap-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
