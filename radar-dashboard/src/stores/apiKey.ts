import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'radar-dashboard/api-key'

export const useApiKeyStore = defineStore('apiKey', () => {
  const apiKey = ref<string>(sessionStorage.getItem(STORAGE_KEY) ?? '')

  function setApiKey(value: string): void {
    apiKey.value = value
    if (value) {
      sessionStorage.setItem(STORAGE_KEY, value)
    } else {
      sessionStorage.removeItem(STORAGE_KEY)
    }
  }

  return { apiKey, setApiKey }
})
