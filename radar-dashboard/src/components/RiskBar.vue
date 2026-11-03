<!-- radar-dashboard/src/components/RiskBar.vue -->
<template>
  <section class="risk-bar" aria-labelledby="risk-bar-title">
    <div class="risk-bar__header">
      <h2 id="risk-bar-title" class="risk-bar__title">Weighted risk</h2>
      <span data-testid="risk-total" class="risk-bar__total">{{ riskIndex }}</span>
      <span class="risk-bar__hint">open findings, weighted by severity</span>
    </div>

    <div
      class="risk-bar__track"
      :class="{ 'risk-bar__track--clear': riskIndex === 0 }"
      aria-hidden="true"
    >
      <span
        v-for="layer in layers"
        :key="layer.severity"
        data-testid="risk-segment"
        :class="`risk-bar__segment risk-bar__segment--${layer.severity.toLowerCase()}`"
        :style="{ flexGrow: layer.weighted }"
      />
    </div>

    <p v-if="riskIndex === 0" class="risk-bar__legend risk-bar__legend--clear">No open finding</p>
    <ul v-else class="risk-bar__legend">
      <li
        v-for="layer in layers"
        :key="layer.severity"
        data-testid="risk-legend-item"
        class="risk-bar__legend-item"
      >
        <span
          :class="`risk-bar__swatch risk-bar__segment--${layer.severity.toLowerCase()}`"
          aria-hidden="true"
        />
        <span class="risk-bar__legend-name">{{ layer.label }}</span>
        {{ layer.count }} x{{ layer.weight }} = {{ layer.weighted }}
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SeverityRiskPoint } from '@/api/client'

const props = defineProps<{ risk: SeverityRiskPoint[]; riskIndex: number }>()

// Heaviest first, matching RiskHistoryChart; weights come from the API, never duplicated here.
const LABELS: Record<string, string> = {
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
}

const layers = computed(() =>
  Object.keys(LABELS)
    .map((severity) => props.risk.find((entry) => entry.severity === severity))
    .filter((entry): entry is SeverityRiskPoint => !!entry && entry.weighted > 0)
    .map((entry) => ({ ...entry, label: LABELS[entry.severity]! })),
)
</script>

<style scoped>
.risk-bar {
  margin-bottom: var(--space-5);
}

.risk-bar__header {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.risk-bar__title {
  font-size: var(--text-subtitle);
  font-weight: var(--weight-semibold);
}

.risk-bar__total {
  font-size: var(--text-title);
  font-weight: var(--weight-semibold);
  font-variant-numeric: tabular-nums;
}

.risk-bar__hint {
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
}

.risk-bar__track {
  display: flex;
  gap: 2px;
  width: 100%;
  height: 0.75rem;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-surface-sunken);
}

.risk-bar__track--clear {
  background: var(--color-accent);
}

.risk-bar__segment {
  flex-basis: 0;
  /* A single low finding next to many critical ones must stay visible. */
  min-width: 3px;
}

.risk-bar__segment--critical {
  background: var(--severity-critical);
}
.risk-bar__segment--high {
  background: var(--severity-high);
}
.risk-bar__segment--medium {
  background: var(--severity-medium);
}
.risk-bar__segment--low {
  background: var(--severity-low);
}

.risk-bar__legend {
  list-style: none;
  padding: 0;
  margin-top: var(--space-2);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-4);
  font-size: var(--text-meta);
  color: var(--color-ink-soft);
  font-variant-numeric: tabular-nums;
}

.risk-bar__legend--clear {
  color: var(--color-ink-soft);
}

.risk-bar__legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.risk-bar__swatch {
  width: 0.625rem;
  height: 0.625rem;
  border-radius: 2px;
}

.risk-bar__legend-name {
  color: var(--color-ink);
  font-weight: var(--weight-medium);
}
</style>
