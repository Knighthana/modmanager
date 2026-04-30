import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/forest' },
  {
    path: '/forest',
    name: 'forest',
    component: () => import('../pages/ForestPage.vue'),
  },
  {
    path: '/conflicts',
    name: 'conflicts',
    component: () => import('../pages/ConflictsPage.vue'),
  },
  {
    path: '/rules',
    name: 'rules',
    component: () => import('../pages/RulesPage.vue'),
  },
  {
    path: '/backup',
    name: 'backup',
    component: () => import('../pages/BackupPage.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
