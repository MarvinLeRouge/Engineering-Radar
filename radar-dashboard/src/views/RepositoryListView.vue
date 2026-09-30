<!-- radar-dashboard/src/views/RepositoryListView.vue -->
<template>
  <div class="repository-list-view">
    <h1>Repositories</h1>
    <p v-if="loading">Loading...</p>
    <p v-else-if="store.listError" class="repository-list-view__error">{{ store.listError }}</p>
    <ul v-else>
      <li v-for="repo in store.list" :key="repo.id">
        <RouterLink :to="`/repositories/${repo.id}`">{{ repo.name }}</RouterLink>
        <ScoreGauge
          :value="repo.global_score"
          :status="repo.audit_status === 'scored' ? 'scored' : 'not_yet_audited'"
        />
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import ScoreGauge from '@/components/ScoreGauge.vue'
import { useRepositoriesStore } from '@/stores/repositories'

const store = useRepositoriesStore()
const loading = ref(true)

onMounted(async () => {
  await store.fetchList()
  loading.value = false
})
</script>
