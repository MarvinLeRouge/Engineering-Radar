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
import { computed, reactive, useId } from 'vue'
import FindingCard from './FindingCard.vue'
import SeverityToggleChip from './SeverityToggleChip.vue'
import type { FindingReport } from '@/api/client'
import { SEVERITY_ORDER } from '@/utils/severity'

const instanceId = useId()

const props = defineProps<{ findings: FindingReport[] }>()
defineEmits<{ updated: [] }>()

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

.criterion-findings__group {
  margin-top: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
</style>
