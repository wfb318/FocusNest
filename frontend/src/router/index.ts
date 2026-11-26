import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../layouts/AppLayout.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../views/AuthView.vue'), meta: { public: true } },
    { path: '/register', name: 'register', component: () => import('../views/AuthView.vue'), meta: { public: true } },
    { path: '/', component: AppLayout, children: [
      { path: '', name: 'dashboard', component: () => import('../views/DashboardView.vue') },
      { path: 'settings', name: 'settings', component: () => import('../views/SettingsView.vue') },
      { path: 'tasks', name: 'tasks', component: () => import('../views/TasksView.vue') },
      { path: 'focus', name: 'focus', component: () => import('../views/FocusView.vue') },
      { path: 'schedule', name: 'schedule', component: () => import('../views/ScheduleView.vue') },
      { path: 'statistics', name: 'statistics', component: () => import('../views/StatisticsView.vue') },
      { path: 'journals', name: 'journals', component: () => import('../views/JournalView.vue') },
      { path: 'notes', name: 'notes', component: () => import('../views/NotesView.vue') },
      { path: 'problems', name: 'problems', component: () => import('../views/ProblemsView.vue') },
      { path: 'documents', name: 'documents', component: () => import('../views/DocumentsView.vue') },
      { path: 'admin', name: 'admin', component: () => import('../views/AdminView.vue'), meta: { admin: true } },
      { path: ':pathMatch(.*)*', component: () => import('../views/NotFoundView.vue') },
    ] },
  ],
})
router.beforeEach(async to => {
  const auth = useAuthStore()
  await auth.initialize()
  if (!to.meta.public && !auth.user) return { name: 'login' }
  if (to.meta.admin && auth.user) {
    try { await auth.reloadProfile() }
    catch { return { name: 'dashboard' } }
    if (auth.user?.role !== 'admin') return { name: 'dashboard' }
  }
  if (to.meta.public && auth.user) return { name: 'dashboard' }
})
export default router
