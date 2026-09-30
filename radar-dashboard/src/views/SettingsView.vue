<template>
  <div class="settings-view">
    <h1>Settings</h1>
    <label>
      API key
      <input v-model="draft" type="password" autocomplete="off" />
    </label>
    <button type="button" @click="save">Save</button>
    <p v-if="saved">Saved.</p>
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
