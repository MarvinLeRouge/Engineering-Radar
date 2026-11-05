<!-- radar-dashboard/src/components/CriterionFindings.vue -->
<template>
  <div class="criterion-findings">
    <div class="criterion-findings__chips">
      <SeverityToggleChip
        v-for="group in severityGroups"
        :key="group.severity"
        :severity="group.severity"
        :count-label="String(group.count)"
        :expanded="expanded.has(group.severity)"
        :controls-id="`${instanceId}-${group.severity}`"
        @toggle="toggle(group.severity)"
      />
    </div>

    <template v-for="group in severityGroups" :key="`${group.severity}-findings`">
      <div
        v-if="expanded.has(group.severity)"
        :id="`${instanceId}-${group.severity}`"
        class="criterion-findings__group"
      >
        <template v-for="fileGroup in group.fileGroups" :key="fileGroup.file ?? 'no-file'">
          <h4 v-if="fileGroup.file" class="criterion-findings__file-heading">
            {{ fileGroup.file }}
          </h4>
          <FindingCard
            v-for="finding in fileGroup.findings"
            :key="finding.id"
            :finding="finding"
            :show-file="!fileGroup.file"
            @updated="$emit('updated')"
          />
        </template>
      </div>
    </template>

    <details
      v-if="criterion.dismissed_count"
      data-testid="dismissed-findings"
      class="criterion-findings__dismissed"
      @toggle="dismissedOpen = ($event.target as HTMLDetailsElement).open"
    >
      <summary>Dismissed as false positive ({{ criterion.dismissed_count }})</summary>
      <div class="criterion-findings__group">
        <FindingCard
          v-for="finding in dismissed"
          :key="finding.id"
          :finding="finding"
          @updated="$emit('updated')"
        />
      </div>
    </details>

    <p v-if="loadError" role="alert" class="criterion-findings__error">{{ loadError }}</p>
    <button
      v-if="remaining > 0 && (expanded.size > 0 || dismissedOpen)"
      type="button"
      data-testid="more-findings"
      class="criterion-findings__more"
      :disabled="loadingMore"
      @click="loadMore"
    >
      More ({{ remaining.toLocaleString() }} remaining)
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import FindingCard from './FindingCard.vue'
import SeverityToggleChip from './SeverityToggleChip.vue'
import { useExpandedSet } from '@/composables/useExpandedSet'
import { getCriterionFindings } from '@/api/client'
import type { CriterionReport, FindingReport } from '@/api/client'
import { SEVERITY_ORDER, isFalsePositive } from '@/utils/severity'

const instanceId = useId()

const props = defineProps<{
  criterion: CriterionReport
  repositoryId: number
  scoringRunId: number
}>()
defineEmits<{ updated: [] }>()

const { expanded, toggle } = useExpandedSet()

interface FileGroup {
  file: string | null
  findings: FindingReport[]
}

// Clusters findings sharing a file together, keyed by each file's first
// appearance in the incoming (severity/magnitude-sorted) list. Findings for
// the same file are never reordered relative to each other, but a file that
// reappears later, non-contiguously, is merged into its earlier cluster --
// file grouping is the point of this function, so it takes priority over
// strict overall order once two findings share a file.
function groupByFile(findings: FindingReport[]): FileGroup[] {
  const order: (string | null)[] = []
  const byFile = new Map<string | null, FindingReport[]>()
  for (const finding of findings) {
    const key = finding.file
    if (!byFile.has(key)) {
      order.push(key)
      byFile.set(key, [])
    }
    byFile.get(key)!.push(finding)
  }
  return order.map((file) => ({ file, findings: byFile.get(file)! }))
}

// The report holds the first page of findings; "More" appends the next pages here.
const extraFindings = ref<FindingReport[]>([])
const loadingMore = ref(false)
const loadError = ref<string | null>(null)
const dismissedOpen = ref(false)
// Bumped on every reload, so a slow response for an outdated report is dropped.
let reloadToken = 0

const findings = computed(() => [...props.criterion.findings, ...extraFindings.value])
const remaining = computed(() => props.criterion.findings_total - findings.value.length)

async function fetchPages(offset: number, count: number): Promise<FindingReport[]> {
  const pages: FindingReport[] = []
  while (pages.length < count) {
    const page = await getCriterionFindings(
      props.repositoryId,
      props.criterion.id,
      props.scoringRunId,
      offset + pages.length,
    )
    if (page.length === 0) break
    pages.push(...page)
  }
  return pages
}

async function loadFindings(offset: number, count: number, append: boolean): Promise<void> {
  const token = ++reloadToken
  loadingMore.value = true
  loadError.value = null
  try {
    const pages = await fetchPages(offset, count)
    if (token !== reloadToken) return
    extraFindings.value = append ? [...extraFindings.value, ...pages] : pages
  } catch (error) {
    if (token === reloadToken) {
      loadError.value = error instanceof Error ? error.message : 'loading findings failed'
      // A failed reload would leave stale verdicts on screen: drop them, "More" brings them back.
      if (!append) extraFindings.value = []
    }
  } finally {
    if (token === reloadToken) loadingMore.value = false
  }
}

function loadMore(): void {
  loadFindings(findings.value.length, 1, true)
}

// A verdict change refetches the whole report: reload the pages already shown so the
// list keeps its length. Another scoring run starts again from its first page.
watch(
  () => [props.criterion, props.scoringRunId] as const,
  ([criterion, scoringRunId], [, previousScoringRunId]) => {
    const shown = extraFindings.value.length
    if (scoringRunId !== previousScoringRunId || shown === 0) {
      reloadToken++
      extraFindings.value = []
      loadingMore.value = false
      return
    }
    loadFindings(criterion.findings.length, shown, false)
  },
)

const dismissed = computed(() => findings.value.filter(isFalsePositive))

const severityGroups = computed(() =>
  SEVERITY_ORDER.map((severity) => {
    const loaded = findings.value.filter((f) => f.severity === severity && !isFalsePositive(f))
    // The count comes from the server: it covers the pages not loaded yet.
    const count = props.criterion.severity_counts[severity] ?? 0
    return { severity, count, fileGroups: groupByFile(loaded) }
  }).filter((group) => group.count > 0),
)
</script>

<style scoped>
.criterion-findings__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.criterion-findings__group {
  margin-top: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.criterion-findings__file-heading {
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--text-meta);
  font-weight: var(--weight-semibold);
  color: var(--color-ink-soft);
  word-break: break-all;
}

.criterion-findings__file-heading:not(:first-child) {
  margin-top: var(--space-2);
}
.criterion-findings__dismissed {
  margin-top: var(--space-3);
  font-size: var(--text-meta);
}

.criterion-findings__dismissed summary {
  cursor: pointer;
  width: fit-content;
  color: var(--color-ink-soft);
}

.criterion-findings__dismissed summary:hover {
  color: var(--color-accent);
}

.criterion-findings__more {
  appearance: none;
  border: none;
  background: none;
  padding: 0;
  margin-top: var(--space-3);
  font-size: var(--text-meta);
  color: var(--color-accent);
  cursor: pointer;
}

.criterion-findings__more:hover:not(:disabled) {
  text-decoration: underline;
}

.criterion-findings__more:disabled {
  color: var(--color-ink-soft);
  cursor: progress;
}

.criterion-findings__error {
  margin-top: var(--space-3);
  font-size: var(--text-meta);
  color: var(--text-danger);
}

.criterion-findings__dismissed .criterion-findings__group {
  padding: var(--space-2);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-sm);
}
</style>
