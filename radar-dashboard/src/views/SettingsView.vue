<template>
  <div class="settings-view">
    <h1 class="settings-view__title">Settings</h1>
    <label class="settings-view__field">
      <span class="settings-view__label">API key</span>
      <input v-model="draft" type="password" autocomplete="off" class="settings-view__input" />
    </label>
    <button type="button" class="settings-view__submit" @click="save">Save</button>
    <p v-if="saved" class="settings-view__confirmation">Saved.</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useApiKeyStore } from '@/stores/apiKey'

const store = useApiKeyStore()
const draft = ref(store.apiKey)
const saved = ref(false)

function save(): void {
  store.setApiKey(draft.value)
  saved.value = true
}
</script>

<style scoped>
.settings-view {
  max-width: 24rem;
}

.settings-view__title {
  font-size: var(--text-display);
  font-weight: var(--weight-bold);
  line-height: var(--leading-tight);
  letter-spacing: -0.01em;
  margin-bottom: var(--space-6);
}

.settings-view__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.settings-view__label {
  font-size: var(--text-meta);
  font-weight: var(--weight-medium);
  color: var(--color-ink-soft);
}

.settings-view__input {
  padding: var(--space-3);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.settings-view__submit {
  appearance: none;
  border: none;
  padding: var(--space-3) var(--space-5);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  color: var(--color-surface);
  font-weight: var(--weight-semibold);
  cursor: pointer;
}

.settings-view__submit:hover {
  filter: brightness(0.92);
}

.settings-view__confirmation {
  margin-top: var(--space-3);
  color: var(--text-success);
  font-weight: var(--weight-medium);
}
</style>
