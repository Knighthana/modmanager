import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/datasource' },
  {
    path: '/datasource',
    name: 'datasource',
    component: () => import('../pages/DataSourcePage.vue'),
  },
  {
    path: '/rules-overview',
    name: 'rules-overview',
    component: () => import('../pages/RulesOverviewPage.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../pages/SettingsPage.vue'),
  },
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
    path: '/operations',
    name: 'operations',
    component: () => import('../pages/OperationsPage.vue'),
  },
  {
    path: '/rule-editor',
    name: 'rule-editor',
    component: () => import('../pages/RuleEditorPage.vue'),
  },
  {
    path: '/compute-prep',
    name: 'compute-prep',
    component: () => import('../pages/ComputePrepPage.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
