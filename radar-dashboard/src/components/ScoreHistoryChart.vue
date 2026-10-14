<!-- radar-dashboard/src/components/ScoreHistoryChart.vue -->
<template>
  <div class="score-history-chart">
    <div class="score-history-chart__header">
      <div>
        <h2
          id="score-history-chart-title"
          ref="titleRef"
          tabindex="-1"
          class="score-history-chart__title"
        >
          {{ headerTitle }}
        </h2>
        <button
          v-if="isDrilledDown"
          type="button"
          class="score-history-chart__back"
          @click="backToOverview"
        >
          ← Back to overview
        </button>
      </div>
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
    <div
      v-if="metrics.length > 1 && points.length > 1"
      class="score-history-chart__metrics"
      role="group"
      aria-label="Metrics to display"
    >
      <button
        v-for="metric in metrics"
        :key="metric.id"
        type="button"
        class="score-history-chart__metric-toggle"
        :aria-pressed="isSelected(metric.id)"
        @click="toggleMetric(metric.id)"
      >
        {{ metric.name }}
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
        :plugins="chartPlugins"
      />
      <!-- Chart.js clicks are mouse/touch-only (canvas has no focusable
      points) -- this list is the keyboard- and screen-reader-operable path
      to the same "view that audit's report" outcome, not decoration. It
      shows the same metrics as the chart (one value per currently selected
      metric, so a drilled-down category is listed on its own, not global);
      the button's click action stays tied to the scoring run regardless,
      since viewing an audit's report is a global action either way. -->
      <details class="score-history-chart__list-disclosure">
        <summary>View as list</summary>
        <ul class="score-history-chart__list">
          <li v-for="point in points" :key="point.scoring_run_id">
            <button type="button" @click="emit('select-point', point.scoring_run_id)">
              {{ formatDate(point.scored_at) }} -- {{ listEntryLabel(point) }}
            </button>
          </li>
        </ul>
      </details>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Tooltip,
  Legend,
} from 'chart.js'
import 'chartjs-adapter-date-fns'
import type { ChartOptions, ChartData, ChartEvent, ActiveElement } from 'chart.js'
import type { ScoreHistoryPoint } from '@/api/client'
import { lastPointValueLabelPlugin } from '@/utils/lastPointValueLabelPlugin'

ChartJS.register(
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Tooltip,
  Legend,
)

const props = defineProps<{ points: ScoreHistoryPoint[] }>()
const emit = defineEmits<{ 'select-point': [scoringRunId: number] }>()

type MetricId = 'global' | number

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

// Generated, not a fixed palette: the golden-angle hue step keeps any
// number of categories visually distinct (no wraparound collision once a
// methodology version grows past a hardcoded palette size), and a fixed
// saturation/lightness keeps every line a similar visual weight. Used only
// for chart lines/legend swatches, never as chip text/border color, so
// WCAG text-contrast rules don't apply to it.
function colorForIndex(index: number): string {
  const hue = (index * 137.508) % 360
  return `hsl(${hue.toFixed(1)}, 65%, 42%)`
}

const zoomed = ref(false)
const selectedMetricIds = ref<Set<MetricId>>(new Set(['global']))
const titleRef = ref<HTMLHeadingElement | null>(null)

// Scoped to this chart instance (vue-chartjs' `plugins` prop), not globally
// registered, so it never draws on any other chart elsewhere in the app.
const chartPlugins = [lastPointValueLabelPlugin]

// "Global" plus every category seen across the history, in first-seen
// order (stable for one methodology version, which is the common case).
const metrics = computed<{ id: MetricId; name: string }[]>(() => {
  const seen = new Map<number, string>()
  for (const point of props.points) {
    for (const category of point.categories) {
      if (!seen.has(category.id)) seen.set(category.id, category.name)
    }
  }
  return [{ id: 'global' as MetricId, name: 'Global score' }, ...Array.from(seen, ([id, name]) => ({ id, name }))]
})

// Stable per-metric color, independent of selection order or count, so a
// category's line color never shifts as other metrics are toggled.
const metricColors = computed<Map<MetricId, string>>(() => {
  const map = new Map<MetricId, string>([['global', cssVar('--color-accent')]])
  let colorIndex = 0
  for (const metric of metrics.value) {
    if (metric.id === 'global') continue
    map.set(metric.id, colorForIndex(colorIndex))
    colorIndex += 1
  }
  return map
})

function isSelected(id: MetricId): boolean {
  return selectedMetricIds.value.has(id)
}

function toggleMetric(id: MetricId): void {
  const next = new Set(selectedMetricIds.value)
  if (next.has(id)) {
    if (next.size === 1) return // at least one metric must stay selected
    next.delete(id)
  } else {
    next.add(id)
  }
  selectedMetricIds.value = next
}

// Drill-down: exactly one non-global metric selected. The "Back to
// overview" affordance resets to the default single-metric view.
const isDrilledDown = computed(
  () => selectedMetricIds.value.size === 1 && !selectedMetricIds.value.has('global'),
)

async function backToOverview(): Promise<void> {
  selectedMetricIds.value = new Set(['global'])
  // The "Back to overview" button unmounts as soon as this runs; move focus
  // to the title so keyboard/screen-reader users don't silently land on
  // <body>.
  await nextTick()
  titleRef.value?.focus()
}

const headerTitle = computed(() => {
  if (isDrilledDown.value) {
    const [id] = selectedMetricIds.value
    return metrics.value.find((metric) => metric.id === id)?.name ?? 'Category history'
  }
  const onlyGlobalSelected =
    selectedMetricIds.value.size === 1 && selectedMetricIds.value.has('global')
  return onlyGlobalSelected ? 'Global score history' : 'Score history'
})

const selectedMetrics = computed(() => metrics.value.filter((metric) => isSelected(metric.id)))

function valueForMetric(point: ScoreHistoryPoint, id: MetricId): number | null {
  if (id === 'global') return point.global_score
  return point.categories.find((category) => category.id === id)?.value ?? null
}

function formatMetricLabel(label: string, value: number | null): string {
  return value === null ? `${label}: not yet audited` : `${label}: ${value.toFixed(1)}`
}

// Mirrors the chart itself (and the tooltip) -- one value per currently
// selected metric, so the keyboard-operable fallback list never falls out
// of sync with what's actually plotted (e.g. a drilled-down category).
function listEntryLabel(point: ScoreHistoryPoint): string {
  return selectedMetrics.value
    .map((metric) => formatMetricLabel(metric.name, valueForMetric(point, metric.id)))
    .join(', ')
}

// floor(min)/ceil(max) over the currently selected metrics' defined scores,
// so a tightly-clustered history (e.g. 6.6-7.6) is actually readable
// instead of squashed into a sliver of the fixed 0-10 range. Falls back to
// the full range when there isn't at least a 1-point spread to zoom into
// (e.g. a single real score, or every score identical) -- a degenerate
// near-zero range would make the chart harder to read, not easier.
const yRange = computed<{ min: number; max: number }>(() => {
  if (!zoomed.value) return { min: 0, max: 10 }
  const scores = props.points
    .flatMap((point) => selectedMetrics.value.map((metric) => valueForMetric(point, metric.id)))
    .filter((value): value is number => value !== null)
  if (scores.length === 0) return { min: 0, max: 10 }
  const min = Math.floor(Math.min(...scores))
  const max = Math.ceil(Math.max(...scores))
  return max - min < 1 ? { min: 0, max: 10 } : { min, max }
})

const chartData = computed<ChartData<'line', { x: number; y: number | null }[]>>(() => ({
  datasets: selectedMetrics.value.map((metric) => ({
    label: metric.name,
    data: props.points.map((p) => ({ x: new Date(p.scored_at).getTime(), y: valueForMetric(p, metric.id) })),
    borderColor: metricColors.value.get(metric.id)!,
    backgroundColor: metricColors.value.get(metric.id)!,
    pointRadius: 4,
    pointHoverRadius: 6,
    spanGaps: true,
  })),
}))

const chartOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  // Room for the last-point value label drawn past the last data point by
  // lastPointValueLabelPlugin; without it, the label is clipped by the
  // canvas edge since the last point sits exactly at the chart's right edge.
  layout: { padding: { right: 44 } },
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
    // Disambiguates lines by label, not color alone, once more than one
    // metric is plotted -- the generated per-category colors can otherwise
    // only be told apart by hovering for a tooltip.
    legend: {
      display: selectedMetrics.value.length > 1,
      labels: { color: cssVar('--color-ink-soft') },
    },
    lastPointValueLabel: { fontFamily: cssVar('--font-sans') },
    tooltip: {
      callbacks: {
        label: (context) => formatMetricLabel(context.dataset.label ?? 'Score', context.parsed.y),
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

.score-history-chart__back {
  appearance: none;
  background: none;
  border: none;
  padding: 0;
  margin-top: var(--space-1);
  font-size: var(--text-meta);
  color: var(--color-accent);
  cursor: pointer;
}

.score-history-chart__back:hover {
  text-decoration: underline;
}

.score-history-chart__metrics {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.score-history-chart__metric-toggle {
  appearance: none;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-meta);
  font-weight: var(--weight-medium);
  color: var(--color-ink-soft);
  cursor: pointer;
}

.score-history-chart__metric-toggle:hover {
  color: var(--color-ink);
  border-color: var(--color-ink-soft);
}

.score-history-chart__metric-toggle[aria-pressed='true'] {
  background: var(--color-accent-soft);
  color: var(--color-accent);
  border-color: var(--color-accent);
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
