<template>
  <div class="evidence-picker">
    <p v-if="loading">Loading evidence...</p>
    <p v-else-if="error" class="evidence-picker__error">{{ error }}</p>
    <p v-else-if="candidates.length === 0" class="evidence-picker__empty">
      No evidence linked to this roadmap item's findings yet.
    </p>
    <ul v-else class="evidence-picker__list">
      <li v-for="candidate in candidates" :key="candidate.id">
        <label>
          <input
            type="radio"
            :name="`evidence-candidate-${props.roadmapItemId}`"
            :value="candidate.id"
            v-model="selectedId"
            @change="emitSelection"
          />
          <strong>{{ candidate.evidence_type }}</strong>
          : {{ preview(candidate.content) }}
        </label>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { EvidenceCandidate } from '@/api/client'
import { getRoadmapItemEvidenceCandidates } from '@/api/client'

const props = defineProps<{ roadmapItemId: number }>()
const emit = defineEmits<{ select: [evidenceId: number] }>()

const candidates = ref<EvidenceCandidate[]>([])
const selectedId = ref<number | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

function preview(content: string): string {
  return content.length > 80 ? `${content.slice(0, 80)}...` : content
}

function emitSelection(): void {
  if (selectedId.value !== null) {
    emit('select', selectedId.value)
  }
}

onMounted(async () => {
  try {
    candidates.value = await getRoadmapItemEvidenceCandidates(props.roadmapItemId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'failed to load evidence'
  } finally {
    loading.value = false
  }
})
</script>
