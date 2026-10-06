<template>
  <div class="evidence-picker">
    <p v-if="loading" class="evidence-picker__status">Loading evidence...</p>
    <p v-else-if="error" class="evidence-picker__error">{{ error }}</p>
    <p v-else-if="candidates.length === 0" class="evidence-picker__empty">
      No evidence linked to this roadmap item's findings yet.
    </p>
    <ul v-else class="evidence-picker__list">
      <li v-for="candidate in candidates" :key="candidate.id" class="evidence-picker__item">
        <label class="evidence-picker__option">
          <input
            type="radio"
            :name="`evidence-candidate-${props.roadmapItemId}`"
            :value="candidate.id"
            v-model="selectedId"
            @change="emitSelection"
          />
          <strong class="evidence-picker__type">{{ candidate.evidence_type }}</strong>
          <span class="evidence-picker__preview">{{ preview(candidate.content) }}</span>
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

<style scoped>
.evidence-picker {
  margin-top: var(--space-4);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--color-surface-sunken);
}

.evidence-picker__status,
.evidence-picker__empty {
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
}

.evidence-picker__error {
  font-size: var(--text-meta);
  color: var(--text-danger);
}

.evidence-picker__list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.evidence-picker__option {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  font-size: var(--text-meta);
  cursor: pointer;
}

.evidence-picker__type {
  font-weight: var(--weight-semibold);
  flex-shrink: 0;
}

.evidence-picker__preview {
  color: var(--color-ink-soft);
  font-family: var(--font-mono);
}
</style>
