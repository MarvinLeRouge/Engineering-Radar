<!-- radar-dashboard/src/views/online/OnlineProfileView.vue -->
<template>
  <div class="online-profile">
    <p v-if="loading" class="online-profile__status" role="status">Loading...</p>
    <p v-else-if="notFound" class="online-profile__status">No published profile here.</p>
    <p v-else-if="error" class="online-profile__error" role="alert">{{ error }}</p>
    <template v-else-if="profile">
      <h1 class="page-title online-profile__title">{{ profile.display_name }}</h1>
      <p v-if="profile.repositories.length === 0" class="online-profile__status">
        No repository published yet.
      </p>
      <ul v-else class="online-profile__list">
        <li
          v-for="repository in profile.repositories"
          :key="repository.slug"
          class="online-profile__row"
        >
          <RouterLink :to="`/u/${profile.slug}/${repository.slug}`" class="online-profile__name">{{
            repository.display_name
          }}</RouterLink>
          <ScoreGauge
            :value="repository.latest_global_score"
            :status="repository.latest_global_score === null ? 'not_yet_audited' : 'scored'"
          />
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import ScoreGauge from '@/components/ScoreGauge.vue'
import { ApiError } from '@/api/client'
import { getProfile, type Profile } from '@/api/online'

const route = useRoute()
const profile = ref<Profile | null>(null)
const loading = ref(true)
const notFound = ref(false)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    profile.value = await getProfile(route.params.user as string)
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) {
      notFound.value = true
    } else {
      error.value = caught instanceof Error ? caught.message : 'unexpected error'
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.online-profile__title {
  margin-bottom: var(--space-6);
}

.online-profile__status {
  color: var(--color-ink-soft);
}

.online-profile__error {
  color: var(--text-danger);
  font-weight: var(--weight-medium);
}

.online-profile__list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--color-border);
}

.online-profile__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-1);
  border-bottom: 1px solid var(--color-border);
}

.online-profile__name {
  font-size: var(--text-subtitle);
  font-weight: var(--weight-medium);
  color: var(--color-ink);
}

.online-profile__name:hover {
  color: var(--color-accent);
}
</style>
