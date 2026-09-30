<!-- radar-dashboard/src/components/CriterionFindings.vue -->
<template>
  <div class="criterion-findings">
    <button
      v-for="group in severityGroups"
      :key="group.severity"
      type="button"
      data-testid="severity-chip"
      :class="`criterion-findings__chip criterion-findings__chip--${group.severity.toLowerCase()}`"
      @click="toggle(group.severity)"
    >
      {{ group.severity }} ({{ group.findings.length }})
    </button>

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
.criterion-findings__chip {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.5rem;
  margin-right: 0.5rem;
  border-radius: 0.25rem;
  border: none;
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
  color: #1a1a1a;
}
.criterion-findings__chip--critical {
  background-color: #eb5757;
  color: #f5f5f5;
}
.criterion-findings__chip--high {
  background-color: #f2994a;
}
.criterion-findings__chip--medium {
  background-color: #f2c94c;
}
.criterion-findings__chip--low {
  background-color: #6fcf97;
}
.criterion-findings__chip--info {
  background-color: #56ccf2;
}
.criterion-findings__group {
  margin-top: 0.5rem;
}
</style>
