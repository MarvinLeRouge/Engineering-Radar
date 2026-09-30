import { createRouter, createWebHistory } from 'vue-router'
import RepositoryListView from '@/views/RepositoryListView.vue'
import RepositoryDetailView from '@/views/RepositoryDetailView.vue'
import SettingsView from '@/views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'repository-list', component: RepositoryListView },
    {
      path: '/repositories/:idSlug',
      name: 'repository-detail',
      component: RepositoryDetailView,
    },
    { path: '/settings', name: 'settings', component: SettingsView },
  ],
})

export default router
