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
      <p v-if="store.reportLoading && !store.report">Loading...</p>
      <p v-else-if="store.reportError" class="repository-detail-view__error">
        {{ store.reportError }}
      </p>
      <template v-else-if="store.report">
        <h1>{{ store.report.repository_name }}</h1>
        <div v-for="category in store.report.categories" :key="category.id" class="category">
          <h2>
            {{ category.name }}
            <ScoreGauge :value="category.value" :status="category.status" />
          </h2>
          <div v-for="criterion in category.criteria" :key="criterion.id" class="criterion">
            <h3>
              {{ criterion.name }}
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
      <p v-if="store.roadmapLoading && !store.roadmap.length">Loading...</p>
      <p v-else-if="store.roadmapError" class="repository-detail-view__error">
        {{ store.roadmapError }}
      </p>
      <ul v-else>
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
