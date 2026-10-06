<template>
  <div class="app-shell">
    <header class="app-shell__header">
      <RouterLink to="/" class="app-shell__brand">radar-dashboard</RouterLink>
      <RouterLink to="/settings" class="app-shell__nav-link">Settings</RouterLink>
    </header>
    <main class="app-shell__main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-shell__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-6);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.app-shell__brand {
  font-size: var(--text-subtitle);
  font-weight: var(--weight-semibold);
  color: var(--color-ink);
}

.app-shell__brand:hover {
  text-decoration: none;
  color: var(--color-accent);
}

.app-shell__nav-link {
  font-size: var(--text-meta);
  font-weight: var(--weight-medium);
  color: var(--color-ink-soft);
}

.app-shell__main {
  flex: 1;
  width: 100%;
  max-width: 64rem;
  margin: 0 auto;
  padding: var(--space-6);
}
</style>
