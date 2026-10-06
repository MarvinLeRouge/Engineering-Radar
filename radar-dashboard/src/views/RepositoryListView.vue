<!-- radar-dashboard/src/views/RepositoryListView.vue -->
<template>
  <div class="repository-list-view">
    <h1 class="repository-list-view__title">Repositories</h1>
    <p v-if="loading" class="repository-list-view__status">Loading...</p>
    <p v-else-if="store.listError" class="repository-list-view__error">{{ store.listError }}</p>
    <p v-else-if="store.list.length === 0" class="repository-list-view__status">
      No repositories audited yet.
    </p>
    <ul v-else class="repository-list-view__list">
      <li v-for="repo in store.list" :key="repo.id" class="repository-list-view__row">
        <RouterLink
          :to="`/repositories/${slugify(repo.name)}-${repo.id}`"
          class="repository-list-view__name"
        >
          {{ repo.name }}
        </RouterLink>
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
import { slugify } from '@/utils/slugify'

const store = useRepositoriesStore()
const loading = ref(true)

onMounted(async () => {
  try {
    await store.fetchList()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.repository-list-view__title {
  font-size: var(--text-display);
  font-weight: var(--weight-bold);
  line-height: var(--leading-tight);
  letter-spacing: -0.01em;
  margin-bottom: var(--space-6);
}

.repository-list-view__status {
  color: var(--color-ink-soft);
}

.repository-list-view__error {
  color: var(--text-danger);
  font-weight: var(--weight-medium);
}

.repository-list-view__list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--color-border);
}

.repository-list-view__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-1);
  border-bottom: 1px solid var(--color-border);
}

.repository-list-view__name {
  font-size: var(--text-subtitle);
  font-weight: var(--weight-medium);
  color: var(--color-ink);
}

.repository-list-view__name:hover {
  color: var(--color-accent);
  text-decoration: none;
}
</style>
