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

    <section v-if="tab === 'report'">
      <p v-if="store.reportLoading">Loading...</p>
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
            <FindingCard
              v-for="finding in criterion.findings"
              :key="finding.id"
              :finding="finding"
              @updated="refetchReport"
            />
          </div>
        </div>
      </template>
    </section>

    <section v-else>
      <p v-if="store.roadmapLoading">Loading...</p>
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
import FindingCard from '@/components/FindingCard.vue'
import RoadmapItemRow from '@/components/RoadmapItemRow.vue'
import { useRepositoriesStore } from '@/stores/repositories'

const route = useRoute()
const store = useRepositoriesStore()
const tab = ref<'report' | 'roadmap'>('report')

const repositoryId = Number(route.params.id)

function refetchReport(): void {
  store.fetchReport(repositoryId)
}

function refetchRoadmap(): void {
  store.fetchRoadmap(repositoryId)
}

onMounted(() => {
  refetchReport()
  refetchRoadmap()
})
</script>
