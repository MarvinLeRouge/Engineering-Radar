<!-- radar-dashboard/src/components/RoadmapItemRow.vue -->
<template>
  <li class="roadmap-item-row">
    <h3 class="roadmap-item-row__title">{{ item.title }}</h3>
    <p class="roadmap-item-row__description">{{ item.description }}</p>
    <p class="roadmap-item-row__status">Status: {{ item.status }}</p>
    <p v-if="item.estimated_effort || item.estimated_impact" class="roadmap-item-row__estimates">
      <span v-if="item.estimated_effort">Effort: {{ item.estimated_effort }}</span>
      <span v-if="item.estimated_impact">Impact: {{ item.estimated_impact }}</span>
    </p>
    <label class="roadmap-item-row__field">
      <span class="roadmap-item-row__field-label">Change status</span>
      <select v-model="targetStatus">
        <option value="TODO">To do</option>
        <option value="IN_PROGRESS">In progress</option>
        <option value="DONE">Done</option>
        <option value="WONT_FIX">Won't fix</option>
      </select>
    </label>
    <EvidencePicker
      v-if="targetStatus === 'DONE' && item.status !== 'DONE'"
      :roadmap-item-id="item.id"
      @select="onEvidenceSelected"
    />
    <button
      type="button"
      class="roadmap-item-row__submit"
      :disabled="!canSubmit"
      @click="submit"
    >
      Apply
    </button>
    <p v-if="errorMessage" class="roadmap-item-row__error">{{ errorMessage }}</p>
  </li>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import EvidencePicker from './EvidencePicker.vue'
import type { RoadmapItemRead } from '@/api/client'
import { ApiError, updateRoadmapItemStatus } from '@/api/client'

const props = defineProps<{ item: RoadmapItemRead }>()
const emit = defineEmits<{ updated: [] }>()

const targetStatus = ref(props.item.status)
const selectedEvidenceId = ref<number | null>(null)
const errorMessage = ref<string | null>(null)

const canSubmit = computed(() => {
  if (targetStatus.value === props.item.status) return false
  if (targetStatus.value === 'DONE') return selectedEvidenceId.value !== null
  return true
})

function onEvidenceSelected(evidenceId: number): void {
  selectedEvidenceId.value = evidenceId
}

async function submit(): Promise<void> {
  errorMessage.value = null
  try {
    if (targetStatus.value === 'DONE') {
      await updateRoadmapItemStatus(props.item.id, targetStatus.value, selectedEvidenceId.value!)
    } else {
      await updateRoadmapItemStatus(props.item.id, targetStatus.value)
    }
    emit('updated')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      errorMessage.value = 'Missing or invalid API key: set it in Settings.'
    } else {
      errorMessage.value = error instanceof Error ? error.message : 'update failed'
    }
  }
}
</script>

<style scoped>
.roadmap-item-row {
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}

.roadmap-item-row__title {
  font-size: var(--text-subtitle);
  font-weight: var(--weight-semibold);
  margin-bottom: var(--space-1);
}

.roadmap-item-row__description {
  color: var(--color-ink-soft);
  margin-bottom: var(--space-2);
}

.roadmap-item-row__status {
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
}

.roadmap-item-row__estimates {
  display: flex;
  gap: var(--space-4);
  font-size: var(--text-meta);
  color: var(--color-ink-faint);
  margin-top: var(--space-1);
}

.roadmap-item-row__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-top: var(--space-4);
}

.roadmap-item-row__field-label {
  font-size: var(--text-meta);
  font-weight: var(--weight-medium);
  color: var(--color-ink-soft);
}

.roadmap-item-row__field select {
  padding: var(--space-2);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  width: fit-content;
}

.roadmap-item-row__submit {
  appearance: none;
  border: none;
  margin-top: var(--space-4);
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  color: var(--color-surface);
  font-weight: var(--weight-semibold);
  cursor: pointer;
}

.roadmap-item-row__submit:disabled {
  background: var(--color-border-strong);
  color: var(--color-ink-faint);
  cursor: not-allowed;
}

.roadmap-item-row__error {
  margin-top: var(--space-2);
  color: var(--text-danger);
  font-size: var(--text-meta);
}
</style>
