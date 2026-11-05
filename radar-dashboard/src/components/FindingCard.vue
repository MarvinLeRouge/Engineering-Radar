<!-- radar-dashboard/src/components/FindingCard.vue -->
<template>
  <div class="finding-card">
    <div class="finding-card__header">
      <span class="finding-card__severity" :class="severityClass">{{ finding.severity }}</span>
      <span class="finding-card__description">{{ finding.description }}</span>
    </div>
    <p v-if="locationLabel" class="finding-card__location">{{ locationLabel }}</p>
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
    <div v-if="isDismissed" class="finding-card__note">
      <label class="finding-card__control finding-card__note-control">
        <span class="finding-card__control-label finding-card__note-label">
          Why
          <svg
            class="finding-card__hint-icon"
            viewBox="0 0 16 16"
            width="12"
            height="12"
            aria-hidden="true"
          >
            <title>{{ NOTE_HINT }}</title>
            <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5" />
            <path d="M8 7.25v4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            <circle cx="8" cy="4.75" r="0.9" fill="currentColor" />
          </svg>
        </span>
        <span class="finding-card__note-field">
          <input
            v-model="note"
            type="text"
            data-testid="verdict-note"
            :list="reasonsId"
            :aria-describedby="hintId"
            maxlength="200"
            placeholder="Add a short reason"
            @input="noteSaved = false"
            @change="submitNote"
          />
          <svg
            v-if="noteSaved"
            data-testid="verdict-note-saved"
            class="finding-card__saved-icon"
            viewBox="0 0 16 16"
            width="16"
            height="16"
            aria-hidden="true"
          >
            <path
              d="M3.5 8.5l3 3 6-7"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </span>
      </label>
      <span :id="hintId" class="finding-card__visually-hidden">{{ NOTE_HINT }}</span>
      <span data-testid="verdict-note-status" role="status" class="finding-card__visually-hidden">{{
        noteSaved ? 'Saved' : ''
      }}</span>
      <datalist :id="reasonsId">
        <option v-for="reason in PRESET_REASONS" :key="reason" :value="reason" />
      </datalist>
    </div>
    <p v-if="errorMessage" class="finding-card__error">{{ errorMessage }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import type { FindingReport } from '@/api/client'
import {
  ApiError,
  updateFindingNote,
  updateFindingStatus,
  updateFindingVerdict,
} from '@/api/client'

// Short on purpose: new reasons are added here deliberately, never from past free text.
const PRESET_REASONS = [
  'Waiting for an upstream fix',
  'Framework convention, used at runtime',
  'Accepted risk, local-only image',
] as const
const NOTE_HINT = 'Free text, or start typing to pick a common reason.'

const props = withDefaults(defineProps<{ finding: FindingReport; showFile?: boolean }>(), {
  showFile: true,
})
const emit = defineEmits<{ updated: [] }>()

const verdict = ref(props.finding.human_verdict)
const status = ref(props.finding.status)
const note = ref(props.finding.verdict_note ?? '')
// Shown once the API confirms the note; cleared as soon as the text is edited again.
const noteSaved = ref(false)
const errorMessage = ref<string | null>(null)

const instanceId = useId()
const reasonsId = `${instanceId}-reasons`
const hintId = `${instanceId}-hint`

// A note explains why a finding was set aside, so it only shows once it is.
const isDismissed = computed(() => verdict.value === 'FALSE_POSITIVE' || status.value !== 'OPEN')

const severityClass = computed(
  () => `finding-card__severity--${props.finding.severity.toLowerCase()}`,
)

// `showFile` is false when a parent already groups findings under their own
// file heading (CriterionFindings.vue); repeating the path on every card
// would be redundant there, but the line number alone still earns its keep.
// Independent of that flag, a finding with a line but no file (a legitimate,
// if unusual, data shape) always falls back to the line-only format.
const locationLabel = computed(() => {
  const { file, line } = props.finding
  if (props.showFile && file) {
    return line ? `${file}:${line}` : file
  }
  return line ? `Line ${line}` : null
})

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

async function submitNote(): Promise<void> {
  errorMessage.value = null
  try {
    await updateFindingNote(props.finding.id, note.value)
    noteSaved.value = true
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
  /* Descriptions embed long file paths that would overflow narrow screens. */
  overflow-wrap: anywhere;
}

.finding-card__location {
  font-family: var(--font-mono);
  font-size: var(--text-meta);
  color: var(--color-ink-faint);
  margin-bottom: var(--space-1);
  word-break: break-all;
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

.finding-card__note {
  margin-top: var(--space-3);
}

.finding-card__note-control {
  max-width: 28rem;
}

.finding-card__note-label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.finding-card__hint-icon {
  flex-shrink: 0;
  color: var(--color-ink-faint);
  cursor: help;
}

.finding-card__note-field {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.finding-card__note-field input {
  flex: 1;
  min-width: 0;
}

.finding-card__saved-icon {
  flex-shrink: 0;
  color: var(--text-success);
  animation: finding-card-saved-in 160ms ease-out;
}

@keyframes finding-card-saved-in {
  from {
    opacity: 0;
    transform: scale(0.6);
  }
}

@media (prefers-reduced-motion: reduce) {
  .finding-card__saved-icon {
    animation: none;
  }
}

.finding-card__note input {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  font-size: var(--text-meta);
}

.finding-card__note input::placeholder {
  color: var(--color-ink-faint);
}

.finding-card__visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.finding-card__error {
  margin-top: var(--space-2);
  color: var(--text-danger);
  font-size: var(--text-meta);
}
</style>
