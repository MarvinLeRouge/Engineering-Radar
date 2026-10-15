<template>
  <span
    class="score-gauge"
    :class="bandClass"
    :title="reasonText ?? undefined"
    tabindex="0"
    @click="toggleReason"
  >
    <span class="score-gauge__value">{{ displayValue }}</span>
    <span v-if="reasonVisible && reasonText" class="score-gauge__reason" role="tooltip">
      {{ reasonText }}
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  value: number | null
  status: 'scored' | 'not_applicable' | 'not_yet_audited'
  naReason?: string | null
}>()

const reasonVisible = ref(false)

function toggleReason(): void {
  if (props.status !== 'scored') {
    reasonVisible.value = !reasonVisible.value
  }
}

const bandClass = computed(() => {
  if (props.status === 'not_applicable') return 'score-gauge--na'
  if (props.status === 'not_yet_audited') return 'score-gauge--pending'

  const value = props.value ?? 0
  if (value >= 8) return 'score-gauge--brightgreen'
  if (value >= 6) return 'score-gauge--green'
  if (value >= 4) return 'score-gauge--yellow'
  if (value >= 2) return 'score-gauge--orange'
  return 'score-gauge--red'
})

const displayValue = computed(() => {
  if (props.status === 'scored' && props.value !== null) {
    return props.value.toFixed(1)
  }
  return props.status === 'not_applicable' ? 'N/A' : '-'
})

const reasonText = computed(() => {
  if (props.status === 'not_applicable') return props.naReason ?? 'not applicable'
  if (props.status === 'not_yet_audited') return 'not yet audited'
  return null
})
</script>

<style scoped>
.score-gauge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 3rem;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-weight: var(--weight-semibold);
  font-size: var(--text-meta);
  color: var(--color-ink);
  position: relative;
}
.score-gauge--brightgreen {
  background-color: var(--score-brightgreen);
}
.score-gauge--green {
  background-color: var(--score-green);
}
.score-gauge--yellow {
  background-color: var(--score-yellow);
}
.score-gauge--orange {
  background-color: var(--score-orange);
}
.score-gauge--red {
  background-color: var(--score-red);
  color: var(--severity-critical-ink);
}
.score-gauge--na {
  background-color: var(--score-na);
  color: var(--severity-critical-ink);
  cursor: pointer;
}
.score-gauge--pending {
  background-color: var(--score-pending);
  color: var(--color-ink-soft);
  cursor: pointer;
}
.score-gauge__reason {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: var(--space-1);
  padding: var(--space-1) var(--space-2);
  background: var(--color-ink);
  color: var(--color-surface);
  font-family: var(--font-sans);
  font-size: var(--text-meta);
  font-weight: var(--weight-regular);
  border-radius: var(--radius-sm);
  white-space: nowrap;
  z-index: 10;
}
</style>
