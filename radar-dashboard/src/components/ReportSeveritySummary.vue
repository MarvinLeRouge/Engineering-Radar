<!-- radar-dashboard/src/components/ReportSeveritySummary.vue -->
<template>
  <div v-if="severityGroups.length" class="report-severity-summary">
    <div class="report-severity-summary__chips">
      <SeverityToggleChip
        v-for="group in severityGroups"
        :key="group.severity"
        :severity="group.severity"
        :count-label="`${group.criteria.length} / ${group.findingCount}`"
        :expanded="expanded.has(group.severity)"
        :controls-id="`${instanceId}-${group.severity}`"
        @toggle="toggle(group.severity)"
      />
    </div>

    <template v-for="group in severityGroups" :key="`${group.severity}-criteria`">
      <ul
        v-if="expanded.has(group.severity)"
        :id="`${instanceId}-${group.severity}`"
        class="report-severity-summary__list"
        :aria-label="`${group.severity} findings by criterion`"
      >
        <li v-for="item in group.criteria" :key="item.criterionId">
          <a data-testid="severity-criterion-link" :href="`#criterion-${item.criterionId}`">
            {{ item.categoryName }} / {{ item.criterionName }}
          </a>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, useId } from 'vue'
import SeverityToggleChip from './SeverityToggleChip.vue'
import type { CategoryReport } from '@/api/client'
import { SEVERITY_ORDER } from '@/utils/severity'

const props = defineProps<{ categories: CategoryReport[] }>()

const instanceId = useId()

const expanded = reactive(new Set<string>())

function toggle(severity: string): void {
  if (expanded.has(severity)) {
    expanded.delete(severity)
  } else {
    expanded.add(severity)
  }
}

const severityGroups = computed(() =>
  SEVERITY_ORDER.map((severity) => {
    const criteria: { criterionId: number; categoryName: string; criterionName: string }[] = []
    let findingCount = 0

    for (const category of props.categories) {
      for (const criterion of category.criteria) {
        const matches = criterion.findings.filter((f) => f.severity === severity)
        if (matches.length === 0) continue
        findingCount += matches.length
        criteria.push({
          criterionId: criterion.id,
          categoryName: category.name,
          criterionName: criterion.name,
        })
      }
    }

    return { severity, criteria, findingCount }
  }).filter((group) => group.criteria.length > 0),
)
</script>

<style scoped>
.report-severity-summary {
  margin-bottom: var(--space-7);
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-border);
}

.report-severity-summary__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.report-severity-summary__list {
  list-style: none;
  padding: 0;
  margin-top: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
</style>
