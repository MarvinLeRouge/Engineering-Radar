<!-- radar-dashboard/src/components/FindingCard.vue -->
<template>
  <div class="finding-card" :class="severityClass">
    <div class="finding-card__header">
      <span class="finding-card__severity">{{ finding.severity }}</span>
      <span class="finding-card__description">{{ finding.description }}</span>
    </div>
    <p v-if="finding.recommendation" class="finding-card__recommendation">
      {{ finding.recommendation }}
    </p>
    <div class="finding-card__controls">
      <label>
        Verdict
        <select data-testid="verdict-select" v-model="verdict" @change="submitVerdict">
          <option value="UNREVIEWED">Unreviewed</option>
          <option value="TRUE_POSITIVE">True positive</option>
          <option value="FALSE_POSITIVE">False positive</option>
        </select>
      </label>
      <label>
        Status
        <select data-testid="status-select" v-model="status" @change="submitStatus">
          <option value="OPEN">Open</option>
          <option value="RESOLVED">Resolved</option>
          <option value="WONT_FIX">Won't fix</option>
        </select>
      </label>
    </div>
    <p v-if="errorMessage" class="finding-card__error">{{ errorMessage }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { FindingReport } from '@/api/client'
import { ApiError, updateFindingStatus, updateFindingVerdict } from '@/api/client'

const props = defineProps<{ finding: FindingReport }>()
const emit = defineEmits<{ updated: [] }>()

const verdict = ref(props.finding.human_verdict)
const status = ref(props.finding.status)
const errorMessage = ref<string | null>(null)

const severityClass = computed(() => `finding-card--${props.finding.severity.toLowerCase()}`)

function handleError(error: unknown): void {
  if (error instanceof ApiError && error.status === 401) {
    errorMessage.value = 'Missing or invalid API key: set it in Settings.'
  } else {
    errorMessage.value = error instanceof Error ? error.message : 'update failed'
  }
}

async function submitVerdict(): Promise<void> {
  errorMessage.value = null
  try {
    await updateFindingVerdict(props.finding.id, verdict.value)
    emit('updated')
  } catch (error) {
    handleError(error)
  }
}

async function submitStatus(): Promise<void> {
  errorMessage.value = null
  try {
    await updateFindingStatus(props.finding.id, status.value)
    emit('updated')
  } catch (error) {
    handleError(error)
  }
}
</script>

<style scoped>
.finding-card {
  border-left: 4px solid transparent;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
}
.finding-card--critical {
  border-left-color: #eb5757;
}
.finding-card--high {
  border-left-color: #f2994a;
}
.finding-card--medium {
  border-left-color: #f2c94c;
}
.finding-card--low {
  border-left-color: #6fcf97;
}
.finding-card--info {
  border-left-color: #56ccf2;
}
.finding-card__error {
  color: #eb5757;
  font-size: 0.875rem;
}
</style>
