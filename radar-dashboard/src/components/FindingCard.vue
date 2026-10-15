<!-- radar-dashboard/src/components/FindingCard.vue -->
<template>
  <div class="finding-card">
    <div class="finding-card__header">
      <span class="finding-card__severity" :class="severityClass">{{ finding.severity }}</span>
      <span class="finding-card__description">{{ finding.description }}</span>
    </div>
    <p v-if="finding.recommendation" class="finding-card__recommendation">
      {{ finding.recommendation }}
    </p>
    <div class="finding-card__controls">
      <label class="finding-card__control">
        <span class="finding-card__control-label">Verdict</span>
        <select data-testid="verdict-select" v-model="verdict" @change="submitVerdict">
          <option value="UNREVIEWED">Unreviewed</option>
          <option value="TRUE_POSITIVE">True positive</option>
          <option value="FALSE_POSITIVE">False positive</option>
        </select>
      </label>
      <label class="finding-card__control">
        <span class="finding-card__control-label">Status</span>
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

const severityClass = computed(() => `finding-card__severity--${props.finding.severity.toLowerCase()}`)

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
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.finding-card__header {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.finding-card__severity {
  flex-shrink: 0;
  padding: 0.1rem var(--space-2);
  border-radius: var(--radius-sm);
  font-size: 0.6875rem;
  font-weight: var(--weight-semibold);
  letter-spacing: 0.02em;
}
.finding-card__severity--critical {
  background: var(--severity-critical);
  color: var(--severity-critical-ink);
}
.finding-card__severity--high {
  background: var(--severity-high);
  color: var(--severity-high-ink);
}
.finding-card__severity--medium {
  background: var(--severity-medium);
  color: var(--severity-medium-ink);
}
.finding-card__severity--low {
  background: var(--severity-low);
  color: var(--severity-low-ink);
}
.finding-card__severity--info {
  background: var(--severity-info);
  color: var(--severity-info-ink);
}

.finding-card__description {
  font-size: var(--text-body);
}

.finding-card__recommendation {
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
  margin-bottom: var(--space-3);
}

.finding-card__controls {
  display: flex;
  gap: var(--space-4);
}

.finding-card__control {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.finding-card__control-label {
  font-size: 0.6875rem;
  font-weight: var(--weight-medium);
  color: var(--color-ink-faint);
}

.finding-card__control select {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.finding-card__error {
  margin-top: var(--space-2);
  color: var(--text-danger);
  font-size: var(--text-meta);
}
</style>
