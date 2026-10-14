<!-- radar-dashboard/src/components/ScoreHistoryChart.vue -->
<template>
  <div class="score-history-chart">
    <div class="score-history-chart__header">
      <h2 id="score-history-chart-title" class="score-history-chart__title">
        Global score history
      </h2>
      <button
        v-if="points.length > 1"
        type="button"
        class="score-history-chart__zoom-toggle"
        :aria-pressed="zoomed"
        @click="zoomed = !zoomed"
      >
        {{ zoomed ? 'Full scale (0-10)' : 'Zoom to data range' }}
      </button>
    </div>
    <p v-if="points.length === 0" class="score-history-chart__status">
      No audit history yet.
    </p>
    <p v-else-if="points.length === 1" class="score-history-chart__status">
      Only one audit so far -- history will appear after the next one.
    </p>
    <template v-else>
      <Line
        data-testid="score-history-canvas"
        aria-labelledby="score-history-chart-title"
        :data="chartData"
        :options="chartOptions"
      />
      <!-- Chart.js clicks are mouse/touch-only (canvas has no focusable
      points) -- this list is the keyboard- and screen-reader-operable path
      to the same "view that audit's report" outcome, not decoration. -->
      <details class="score-history-chart__list-disclosure">
        <summary>View as list</summary>
        <ul class="score-history-chart__list">
          <li v-for="point in points" :key="point.scoring_run_id">
            <button type="button" @click="emit('select-point', point.scoring_run_id)">
              {{ formatDate(point.scored_at) }} --
              {{ point.global_score === null ? 'not yet audited' : point.global_score.toFixed(1) }}
            </button>
          </li>
        </ul>
      </details>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Tooltip,
} from 'chart.js'
import 'chartjs-adapter-date-fns'
import type { ChartOptions, ChartData, ChartEvent, ActiveElement } from 'chart.js'
import type { ScoreHistoryPoint } from '@/api/client'

ChartJS.register(LineController, LineElement, PointElement, LinearScale, TimeScale, Tooltip)

const props = defineProps<{ points: ScoreHistoryPoint[] }>()
const emit = defineEmits<{ 'select-point': [scoringRunId: number] }>()

// tokens.css has a single static :root block, no dark-mode/media-query
// mechanism -- these are read once per computed re-evaluation but are not
// meant to be reactive to anything. If theme switching is ever added, this
// needs revisiting; it is not a bug today.
function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function formatDate(scoredAt: string): string {
  return new Date(scoredAt).toLocaleDateString()
}

const zoomed = ref(false)

// floor(min)/ceil(max) over the defined scores, so a tightly-clustered
// history (e.g. 6.6-7.6) is actually readable instead of squashed into a
// sliver of the fixed 0-10 range. Falls back to the full range when there
// isn't at least a 1-point spread to zoom into (e.g. a single real score,
// or every score identical) -- a degenerate near-zero range would make the
// chart harder to read, not easier.
const yRange = computed<{ min: number; max: number }>(() => {
  if (!zoomed.value) return { min: 0, max: 10 }
  const scores = props.points
    .map((p) => p.global_score)
    .filter((value): value is number => value !== null)
  if (scores.length === 0) return { min: 0, max: 10 }
  const min = Math.floor(Math.min(...scores))
  const max = Math.ceil(Math.max(...scores))
  return max - min < 1 ? { min: 0, max: 10 } : { min, max }
})

const chartData = computed<ChartData<'line', { x: number; y: number | null }[]>>(() => ({
  datasets: [
    {
      label: 'Global score',
      data: props.points.map((p) => ({ x: new Date(p.scored_at).getTime(), y: p.global_score })),
      borderColor: cssVar('--color-accent'),
      backgroundColor: cssVar('--color-accent'),
      pointRadius: 4,
      pointHoverRadius: 6,
      spanGaps: true,
    },
  ],
}))

const chartOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  scales: {
    x: {
      type: 'time',
      time: { unit: 'day' },
      grid: { color: cssVar('--color-border') },
      ticks: { color: cssVar('--color-ink-soft') },
    },
    y: {
      min: yRange.value.min,
      max: yRange.value.max,
      grid: { color: cssVar('--color-border') },
      ticks: { color: cssVar('--color-ink-soft') },
    },
  },
  plugins: {
    tooltip: {
      callbacks: {
        label: (context) => {
          const value = context.parsed.y
          return value === null ? 'Not yet audited' : `Score: ${value.toFixed(1)}`
        },
      },
    },
  },
  onClick: (_event: ChartEvent, elements: ActiveElement[]) => {
    const element = elements[0]
    if (!element) return
    const point = props.points[element.index]
    if (point) emit('select-point', point.scoring_run_id)
  },
}))
</script>

<style scoped>
.score-history-chart__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.score-history-chart__title {
  font-size: var(--text-subtitle);
  font-weight: var(--weight-semibold);
}

.score-history-chart__zoom-toggle {
  appearance: none;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-meta);
  font-weight: var(--weight-medium);
  color: var(--color-ink-soft);
  cursor: pointer;
  flex-shrink: 0;
}

.score-history-chart__zoom-toggle:hover {
  color: var(--color-ink);
  border-color: var(--color-ink-soft);
}

.score-history-chart__zoom-toggle[aria-pressed='true'] {
  background: var(--color-accent-soft);
  color: var(--color-accent);
  border-color: var(--color-accent);
}

.score-history-chart__status {
  color: var(--color-ink-soft);
}

.score-history-chart__list-disclosure {
  margin-top: var(--space-3);
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
}

.score-history-chart__list-disclosure summary {
  cursor: pointer;
  color: var(--color-accent);
}

.score-history-chart__list {
  list-style: none;
  padding: 0;
  margin-top: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.score-history-chart__list button {
  appearance: none;
  background: none;
  border: none;
  padding: 0;
  color: var(--color-ink);
  cursor: pointer;
  text-align: left;
}

.score-history-chart__list button:hover {
  color: var(--color-accent);
}
</style>
