<!-- radar-dashboard/src/components/SeverityToggleChip.vue -->
<template>
  <button
    type="button"
    data-testid="severity-chip"
    :class="`severity-toggle-chip severity-toggle-chip--${severity.toLowerCase()}`"
    :aria-expanded="expanded"
    :aria-controls="controlsId"
    @click="$emit('toggle')"
  >
    {{ severity }} ({{ countLabel }})
    <span
      data-testid="chip-arrow"
      class="severity-toggle-chip__arrow"
      :class="{ 'severity-toggle-chip__arrow--open': expanded }"
    />
  </button>
</template>

<script setup lang="ts">
import type { Severity } from '@/utils/severity'

defineProps<{
  severity: Severity
  countLabel: string
  expanded: boolean
  controlsId?: string
}>()
defineEmits<{ toggle: [] }>()
</script>

<style scoped>
.severity-toggle-chip {
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
.severity-toggle-chip--critical {
  background-color: var(--severity-critical);
  color: var(--severity-critical-ink);
}
.severity-toggle-chip--high {
  background-color: var(--severity-high);
  color: var(--severity-high-ink);
}
.severity-toggle-chip--medium {
  background-color: var(--severity-medium);
  color: var(--severity-medium-ink);
}
.severity-toggle-chip--low {
  background-color: var(--severity-low);
  color: var(--severity-low-ink);
}
.severity-toggle-chip--info {
  background-color: var(--severity-info);
  color: var(--severity-info-ink);
}

.severity-toggle-chip__arrow {
  display: inline-block;
  width: 0;
  height: 0;
  border-left: 0.3rem solid transparent;
  border-right: 0.3rem solid transparent;
  border-top: 0.35rem solid currentColor;
  transition: transform 0.15s ease;
  vertical-align: middle;
}
.severity-toggle-chip__arrow--open {
  transform: rotate(-180deg);
}
</style>
