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
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-weight: 600;
  color: #1a1a1a;
  position: relative;
}
.score-gauge--brightgreen {
  background-color: #2ecc71;
}
.score-gauge--green {
  background-color: #6fcf97;
}
.score-gauge--yellow {
  background-color: #f2c94c;
}
.score-gauge--orange {
  background-color: #f2994a;
}
.score-gauge--red {
  background-color: #eb5757;
  color: #f5f5f5;
}
.score-gauge--na {
  background-color: #9a9a9a;
  color: #f5f5f5;
  cursor: pointer;
}
.score-gauge--pending {
  background-color: #d4d4d4;
  color: #4a4a4a;
  cursor: pointer;
}
.score-gauge__reason {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 0.25rem;
  padding: 0.25rem 0.5rem;
  background: #1a1a1a;
  color: #fff;
  font-size: 0.75rem;
  font-weight: 400;
  border-radius: 0.25rem;
  white-space: nowrap;
  z-index: 10;
}
</style>
