<!-- radar-dashboard/src/components/ChartPointList.vue -->
<template>
  <details class="chart-point-list">
    <summary>View as list</summary>
    <ul class="chart-point-list__items" data-testid="chart-point-list">
      <li v-for="point in points" :key="point.scoring_run_id">
        <button
          type="button"
          :class="{ 'chart-point-list__button--tabular': tabularNums }"
          @click="emit('select-point', point.scoring_run_id)"
        >
          {{ formatDate(point.scored_at) }} -- {{ label(point) }}
        </button>
      </li>
    </ul>
  </details>
</template>

<script setup lang="ts">
import type { ScoreHistoryPoint } from '@/api/client'

/**
 * Keyboard- and screen-reader-operable list of a history chart's points:
 * one button per scoring run, emitting `select-point` like a click on the chart.
 */
defineProps<{
  points: ScoreHistoryPoint[]
  label: (point: ScoreHistoryPoint) => string
  tabularNums?: boolean
}>()
const emit = defineEmits<{ 'select-point': [scoringRunId: number] }>()

function formatDate(scoredAt: string): string {
  return new Date(scoredAt).toLocaleDateString()
}
</script>

<style scoped>
.chart-point-list {
  margin-top: var(--space-3);
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
}

.chart-point-list summary {
  cursor: pointer;
  color: var(--color-accent);
}

.chart-point-list__items {
  list-style: none;
  padding: 0;
  margin-top: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.chart-point-list__items button {
  appearance: none;
  background: none;
  border: none;
  padding: 0;
  color: var(--color-ink);
  cursor: pointer;
  text-align: left;
}

.chart-point-list__button--tabular {
  font-variant-numeric: tabular-nums;
}

.chart-point-list__items button:hover {
  color: var(--color-accent);
}
</style>
