<!-- radar-dashboard/src/components/RoadmapItemRow.vue -->
<template>
  <li class="roadmap-item-row">
    <h3>{{ item.title }}</h3>
    <p>{{ item.description }}</p>
    <p class="roadmap-item-row__status">Status: {{ item.status }}</p>
    <p v-if="item.estimated_effort || item.estimated_impact" class="roadmap-item-row__estimates">
      <span v-if="item.estimated_effort">Effort: {{ item.estimated_effort }}</span>
      <span v-if="item.estimated_impact">Impact: {{ item.estimated_impact }}</span>
    </p>
    <label>
      Change status
      <select v-model="targetStatus">
        <option value="TODO">To do</option>
        <option value="IN_PROGRESS">In progress</option>
        <option value="DONE">Done</option>
        <option value="WONT_FIX">Won't fix</option>
      </select>
    </label>
    <EvidencePicker
      v-if="targetStatus === 'DONE'"
      :roadmap-item-id="item.id"
      @select="onEvidenceSelected"
    />
    <button type="button" :disabled="!canSubmit" @click="submit">Apply</button>
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
