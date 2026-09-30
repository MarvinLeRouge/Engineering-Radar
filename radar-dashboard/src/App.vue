<template>
  <div class="app-shell">
    <header class="app-shell__header">
      <RouterLink to="/">radar-dashboard</RouterLink>
      <RouterLink to="/settings">Settings</RouterLink>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>
