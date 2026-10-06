<!-- radar-dashboard/src/components/CriterionFindings.vue -->
<template>
  <div class="criterion-findings">
    <div class="criterion-findings__chips">
      <button
        v-for="group in severityGroups"
        :key="group.severity"
        type="button"
        data-testid="severity-chip"
        :class="`criterion-findings__chip criterion-findings__chip--${group.severity.toLowerCase()}`"
        :aria-expanded="expanded.has(group.severity)"
        @click="toggle(group.severity)"
      >
        {{ group.severity }} ({{ group.findings.length }})
        <span
          data-testid="chip-arrow"
          class="criterion-findings__arrow"
          :class="{ 'criterion-findings__arrow--open': expanded.has(group.severity) }"
        />
      </button>
    </div>

    <template v-for="group in severityGroups" :key="`${group.severity}-findings`">
      <div v-if="expanded.has(group.severity)" class="criterion-findings__group">
        <FindingCard
          v-for="finding in group.findings"
          :key="finding.id"
          :finding="finding"
          @updated="$emit('updated')"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import FindingCard from './FindingCard.vue'
import type { FindingReport } from '@/api/client'

const props = defineProps<{ findings: FindingReport[] }>()
defineEmits<{ updated: [] }>()

const SEVERITY_ORDER: FindingReport['severity'][] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']

const expanded = reactive(new Set<string>())

function toggle(severity: string): void {
  if (expanded.has(severity)) {
    expanded.delete(severity)
  } else {
    expanded.add(severity)
  }
}

const severityGroups = computed(() =>
  SEVERITY_ORDER.map((severity) => ({
    severity,
    findings: props.findings.filter((f) => f.severity === severity),
  })).filter((group) => group.findings.length > 0),
)
</script>

<style scoped>
.criterion-findings__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.criterion-findings__chip {
  appearance: none;
  border: none;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-meta);
  font-weight: var(--weight-semibold);
  font-variant-numeric: tabular-nums;
  cursor: pointer;
}
.criterion-findings__chip--critical {
  background-color: var(--severity-critical);
  color: var(--severity-critical-ink);
}
.criterion-findings__chip--high {
  background-color: var(--severity-high);
  color: var(--severity-high-ink);
}
.criterion-findings__chip--medium {
  background-color: var(--severity-medium);
  color: var(--severity-medium-ink);
}
.criterion-findings__chip--low {
  background-color: var(--severity-low);
  color: var(--severity-low-ink);
}
.criterion-findings__chip--info {
  background-color: var(--severity-info);
  color: var(--severity-info-ink);
}

.criterion-findings__group {
  margin-top: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.criterion-findings__arrow {
  display: inline-block;
  width: 0;
  height: 0;
  border-left: 0.3rem solid transparent;
  border-right: 0.3rem solid transparent;
  border-top: 0.35rem solid currentColor;
  transition: transform 0.15s ease;
  vertical-align: middle;
}
.criterion-findings__arrow--open {
  transform: rotate(-180deg);
}
</style>
