<!-- radar-dashboard/src/components/PublishReportDialog.vue -->
<template>
  <button
    type="button"
    class="button-secondary publish-report__open"
    data-testid="publish-open"
    @click="open"
  >
    Publish online
  </button>

  <dialog
    ref="dialog"
    class="publish-report"
    aria-labelledby="publish-report-title"
    @close="onClose"
  >
    <header class="publish-report__header">
      <h2 id="publish-report-title" class="publish-report__title">Publish to radar-online</h2>
      <p class="publish-report__lead">
        Only these scores leave this machine: no finding, path or note.
      </p>
    </header>

    <p v-if="loading" class="publish-report__status" role="status">Loading preview...</p>

    <template v-else-if="preview">
      <dl class="publish-report__facts">
        <div>
          <dt>Repository</dt>
          <dd>
            {{ preview.payload.repository.display_name }}
            <code>{{ preview.payload.repository.slug }}</code>
          </dd>
        </div>
        <div>
          <dt>Commit</dt>
          <dd>
            <code :title="preview.payload.commit_sha">{{ shortSha }}</code>
          </dd>
        </div>
        <div>
          <dt>Scored on</dt>
          <dd>{{ formatDate(preview.payload.scored_at) }}</dd>
        </div>
        <div>
          <dt>Global score</dt>
          <dd>
            <ScoreGauge
              :value="preview.payload.global_score"
              :status="preview.payload.global_score === null ? 'not_yet_audited' : 'scored'"
            />
          </dd>
        </div>
      </dl>

      <ul class="publish-report__categories">
        <li v-for="category in preview.payload.categories" :key="category.name">
          <span>{{ category.name }}</span>
          <ScoreGauge
            v-if="category.implemented"
            :value="category.value"
            :status="category.status"
          />
          <span v-else class="publish-report__not-implemented">Not implemented yet</span>
        </li>
      </ul>

      <p v-if="preview.is_dirty" class="publish-report__warning" role="alert">
        This audit scored uncommitted changes, so its commit does not describe the scored code.
        Commit or stash them, audit and score again, then publish.
      </p>
    </template>

    <p v-if="errorMessage" class="publish-report__error" role="alert">{{ errorMessage }}</p>

    <p v-if="reportUrl" class="publish-report__success" role="status">
      Published.
      <a :href="reportUrl" target="_blank" rel="noopener" data-testid="publish-link">
        View the public report
      </a>
    </p>

    <footer class="publish-report__actions">
      <button
        type="button"
        class="button-secondary publish-report__action"
        data-testid="publish-cancel"
        @click="close"
      >
        {{ reportUrl ? 'Close' : 'Cancel' }}
      </button>
      <button
        v-if="canPublish"
        type="button"
        class="button-primary publish-report__action"
        data-testid="publish-confirm"
        :disabled="publishing"
        @click="publish"
      >
        {{ publishing ? 'Publishing...' : 'Publish' }}
      </button>
    </footer>
  </dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import ScoreGauge from './ScoreGauge.vue'
import { ApiError, getPublishPreview, publishRepository } from '@/api/client'
import type { PublishPreview } from '@/api/client'

const props = defineProps<{ repositoryId: number }>()

const dialog = ref<HTMLDialogElement | null>(null)
const preview = ref<PublishPreview | null>(null)
const loading = ref(false)
const publishing = ref(false)
const errorMessage = ref<string | null>(null)
const reportUrl = ref<string | null>(null)

const shortSha = computed(() => preview.value?.payload.commit_sha.slice(0, 7) ?? '')
const canPublish = computed(
  () => preview.value !== null && !preview.value.is_dirty && reportUrl.value === null,
)

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString()
}

function explain(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Missing or invalid API key: set it in Settings.'
    if (error.status === 503) {
      return 'Publishing is not configured: set RADAR_ONLINE_URL and RADAR_ONLINE_API_KEY in .env, then restart radar-api.'
    }
    return error.message
  }
  return error instanceof Error ? error.message : 'publishing failed'
}

async function open(): Promise<void> {
  preview.value = null
  errorMessage.value = null
  reportUrl.value = null
  loading.value = true
  dialog.value?.showModal()
  try {
    preview.value = await getPublishPreview(props.repositoryId)
  } catch (error) {
    errorMessage.value = explain(error)
  } finally {
    loading.value = false
  }
}

async function publish(): Promise<void> {
  errorMessage.value = null
  publishing.value = true
  try {
    reportUrl.value = (await publishRepository(props.repositoryId)).report_url
  } catch (error) {
    errorMessage.value = explain(error)
  } finally {
    publishing.value = false
  }
}

function close(): void {
  dialog.value?.close()
}

function onClose(): void {
  publishing.value = false
}
</script>

<style scoped>
.publish-report__open {
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-meta);
}

.publish-report {
  width: min(32rem, calc(100vw - 2 * var(--space-4)));
  max-height: calc(100dvh - 2 * var(--space-6));
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-ink);
  box-shadow: 0 12px 32px rgb(26 31 38 / 18%);
}

/* Header, messages and actions stay visible; only the category list scrolls. */
.publish-report[open] {
  display: flex;
  flex-direction: column;
}

.publish-report::backdrop {
  background: rgb(26 31 38 / 40%);
}

.publish-report__header {
  margin-bottom: var(--space-5);
}

.publish-report__title {
  font-size: var(--text-title);
  font-weight: var(--weight-semibold);
  line-height: var(--leading-tight);
  margin-bottom: var(--space-2);
}

.publish-report__lead,
.publish-report__status {
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
}

.publish-report__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  margin: 0 0 var(--space-5);
}

.publish-report__facts dt {
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
  margin-bottom: var(--space-1);
}

.publish-report__facts dd {
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  font-weight: var(--weight-medium);
}

.publish-report__facts code {
  font-family: var(--font-mono);
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
}

.publish-report__categories {
  flex: 1 1 auto;
  min-height: 6rem;
  overflow-y: auto;
  list-style: none;
  padding: 0;
  margin: 0 0 var(--space-5);
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}

.publish-report__categories li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-1) var(--space-2) 0;
  font-size: var(--text-body);
}

.publish-report__categories li + li {
  border-top: 1px solid var(--color-border);
}

.publish-report__not-implemented {
  padding: var(--space-1) var(--space-2);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-size: var(--text-meta);
  font-weight: var(--weight-medium);
  color: var(--color-ink-faint);
  white-space: nowrap;
}

.publish-report__warning,
.publish-report__error {
  margin-bottom: var(--space-4);
  font-weight: var(--weight-medium);
  color: var(--text-danger);
}

.publish-report__success {
  margin-bottom: var(--space-4);
  font-weight: var(--weight-medium);
  color: var(--text-success);
}

.publish-report__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

.publish-report__action {
  padding: var(--space-2) var(--space-4);
}

.publish-report__action:disabled {
  opacity: 0.6;
  cursor: progress;
}

@media (max-width: 30rem) {
  .publish-report__facts {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
