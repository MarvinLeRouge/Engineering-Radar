<!-- radar-dashboard/src/components/RiskHistoryChart.vue -->
<template>
  <div class="risk-history-chart">
    <h2 id="risk-history-chart-title" class="risk-history-chart__title">Weighted risk history</h2>
    <p class="risk-history-chart__caption">
      Open findings weighted by severity<template v-if="weightsLabel">: {{ weightsLabel }}</template
      >. Resolved, won't-fix and false-positive findings are excluded.
    </p>
    <p v-if="points.length < 2" class="risk-history-chart__status">
      Only one audit so far -- history will appear after the next one.
    </p>
    <template v-else>
      <div class="risk-history-chart__canvas">
        <Line
          data-testid="risk-history-canvas"
          role="img"
          aria-labelledby="risk-history-chart-title"
          :data="chartData"
          :options="chartOptions"
        />
      </div>
      <ChartPointList
        :points="points"
        :label="listEntryLabel"
        tabular-nums
        @select-point="emit('select-point', $event)"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import ChartPointList from './ChartPointList.vue'
import {
  Chart as ChartJS,
  Filler,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Tooltip,
  Legend,
} from 'chart.js'
import 'chartjs-adapter-date-fns'
import type { ChartOptions, ChartData, ChartEvent, ActiveElement, TooltipItem } from 'chart.js'
import type { ScoreHistoryPoint, SeverityRiskPoint } from '@/api/client'

ChartJS.register(
  Filler,
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

// Heaviest layer first so it sits on the axis and reads without stacking offset.
// Weights come from the API (radar_core SEVERITY_RISK_WEIGHT), never duplicated here.
const LAYERS = [
  { severity: 'CRITICAL', label: 'Critical', token: '--severity-critical' },
  { severity: 'HIGH', label: 'High', token: '--severity-high' },
  { severity: 'MEDIUM', label: 'Medium', token: '--severity-medium' },
  { severity: 'LOW', label: 'Low', token: '--severity-low' },
] as const

// Severity tokens are #rrggbb; a hex alpha suffix stays valid for canvas fillStyle.
const FILL_ALPHA_HEX = '8c'

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function entryFor(point: ScoreHistoryPoint, severity: string): SeverityRiskPoint | undefined {
  return point.risk.find((entry) => entry.severity === severity)
}

const weightsLabel = computed(() => {
  const latest = props.points[props.points.length - 1]
  if (!latest) return ''
  return LAYERS.map(
    (layer) => `${layer.label.toLowerCase()} x${entryFor(latest, layer.severity)?.weight ?? 0}`,
  ).join(', ')
})

function listEntryLabel(point: ScoreHistoryPoint): string {
  const counts = LAYERS.map(
    (layer) => `${entryFor(point, layer.severity)?.count ?? 0} ${layer.label.toLowerCase()}`,
  ).join(', ')
  return `risk index ${point.risk_index} (${counts})`
}

const chartData = computed<ChartData<'line', { x: number; y: number }[]>>(() => ({
  datasets: LAYERS.map((layer, index) => {
    const color = cssVar(layer.token)
    return {
      label: layer.label,
      data: props.points.map((point) => ({
        x: new Date(point.scored_at).getTime(),
        y: entryFor(point, layer.severity)?.weighted ?? 0,
      })),
      fill: index === 0 ? 'origin' : '-1',
      borderColor: color,
      backgroundColor: `${color}${FILL_ALPHA_HEX}`,
      borderWidth: 1.5,
      // Several audits a day are common: markers only on hover keep the areas readable.
      pointRadius: 0,
      pointHoverRadius: 4,
    }
  }),
}))

function tooltipLabel(context: Pick<TooltipItem<'line'>, 'datasetIndex' | 'dataIndex'>): string {
  const layer = LAYERS[context.datasetIndex]!
  const entry = entryFor(props.points[context.dataIndex]!, layer.severity)
  const excluded = entry?.excluded ? ` (+${entry.excluded} excluded)` : ''
  return `${layer.label}: ${entry?.count ?? 0} open x ${entry?.weight ?? 0} = ${entry?.weighted ?? 0}${excluded}`
}

function tooltipFooter(items: Pick<TooltipItem<'line'>, 'dataIndex'>[]): string {
  const point = items[0] ? props.points[items[0].dataIndex] : undefined
  return point ? `Risk index: ${point.risk_index}` : ''
}

const chartOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  scales: {
    x: {
      type: 'time',
      time: { unit: 'day' },
      grid: { color: cssVar('--color-border') },
      ticks: { color: cssVar('--color-ink-soft') },
    },
    y: {
      stacked: true,
      beginAtZero: true,
      grid: { color: cssVar('--color-border') },
      ticks: { color: cssVar('--color-ink-soft') },
    },
  },
  plugins: {
    legend: { labels: { color: cssVar('--color-ink-soft') } },
    tooltip: {
      // Stack order reads top-down like the chart: low on top, critical at the base.
      itemSort: (a, b) => b.datasetIndex - a.datasetIndex,
      callbacks: { label: tooltipLabel, footer: tooltipFooter },
    },
  },
  onClick: (_event: ChartEvent, elements: ActiveElement[]) => {
    const point = elements[0] ? props.points[elements[0].index] : undefined
    if (point) emit('select-point', point.scoring_run_id)
  },
}))
</script>

<style scoped>
.risk-history-chart {
  margin-top: var(--space-6);
}

.risk-history-chart__title {
  font-size: var(--text-subtitle);
  font-weight: var(--weight-semibold);
}

.risk-history-chart__caption {
  margin: var(--space-1) 0 var(--space-4);
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
  max-width: 70ch;
}

.risk-history-chart__canvas {
  position: relative;
  height: 22rem;
}

@media (max-width: 640px) {
  .risk-history-chart__canvas {
    height: 18rem;
  }
}

.risk-history-chart__status {
  color: var(--color-ink-soft);
}
</style>
