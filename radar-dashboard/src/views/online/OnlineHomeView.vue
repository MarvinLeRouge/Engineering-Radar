<!-- radar-dashboard/src/views/online/OnlineHomeView.vue -->
<template>
  <div class="online-home">
    <h1 class="page-title online-home__title">Engineering-Radar reports</h1>
    <p class="online-home__lead">
      Global and category quality scores that developers publish for their own repositories, from
      their own Engineering-Radar audits. Every score here is self-assessed: no finding, file path
      or note ever leaves the author's machine.
    </p>
    <p class="online-home__lead">
      Reports live at <code>/u/&lt;user&gt;/&lt;repository&gt;</code>. Engineering-Radar itself is
      open source:
      <a href="https://github.com/MarvinLeRouge/Engineering-Radar" rel="noopener">
        how the scores are computed</a
      >.
    </p>
  </div>
</template>

<style scoped>
.online-home {
  max-width: 40rem;
}

.online-home__title {
  margin-bottom: var(--space-5);
}

.online-home__lead {
  font-size: var(--text-body);
  line-height: var(--leading-normal);
  color: var(--color-ink-soft);
  margin-bottom: var(--space-4);
}

.online-home__lead code {
  font-family: var(--font-mono);
  font-size: var(--text-meta);
  color: var(--color-ink);
}
</style>
