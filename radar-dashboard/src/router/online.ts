import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import OnlineHomeView from '@/views/online/OnlineHomeView.vue'
import OnlineProfileView from '@/views/online/OnlineProfileView.vue'
import OnlineReportView from '@/views/online/OnlineReportView.vue'

// Public pages only: the local views (findings, verdicts, roadmap, settings) are never
// imported here, so they are not part of the online bundle at all.
export const onlineRoutes: RouteRecordRaw[] = [
  { path: '/', name: 'online-home', component: OnlineHomeView },
  { path: '/u/:user', name: 'online-profile', component: OnlineProfileView },
  { path: '/u/:user/:repo', name: 'online-report', component: OnlineReportView },
]

export function createOnlineRouter() {
  return createRouter({ history: createWebHistory(), routes: onlineRoutes })
}
