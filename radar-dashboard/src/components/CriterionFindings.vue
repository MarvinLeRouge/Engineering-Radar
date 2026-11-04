<!-- radar-dashboard/src/components/CriterionFindings.vue -->
<template>
  <div class="criterion-findings">
    <div class="criterion-findings__chips">
      <SeverityToggleChip
        v-for="group in severityGroups"
        :key="group.severity"
        :severity="group.severity"
        :count-label="String(group.findings.length)"
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
      v-if="dismissed.length"
      data-testid="dismissed-findings"
      class="criterion-findings__dismissed"
    >
      <summary>Dismissed as false positive ({{ dismissed.length }})</summary>
      <div class="criterion-findings__group">
        <FindingCard
          v-for="finding in dismissed"
          :key="finding.id"
          :finding="finding"
          @updated="$emit('updated')"
        />
      </div>
    </details>
  </div>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue'
import FindingCard from './FindingCard.vue'
import SeverityToggleChip from './SeverityToggleChip.vue'
import { useExpandedSet } from '@/composables/useExpandedSet'
import type { FindingReport } from '@/api/client'
import { SEVERITY_ORDER, isFalsePositive } from '@/utils/severity'

const instanceId = useId()

const props = defineProps<{ findings: FindingReport[] }>()
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

const dismissed = computed(() => props.findings.filter(isFalsePositive))

const severityGroups = computed(() =>
  SEVERITY_ORDER.map((severity) => {
    const findings = props.findings.filter((f) => f.severity === severity && !isFalsePositive(f))
    return { severity, findings, fileGroups: groupByFile(findings) }
  }).filter((group) => group.findings.length > 0),
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

.criterion-findings__dismissed .criterion-findings__group {
  padding: var(--space-2);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-sm);
}
</style>
