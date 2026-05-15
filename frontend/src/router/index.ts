import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  // ── Workspace hub (default home) ──
  {
    path: '/',
    name: 'workspace-list',
    component: () => import('../pages/WorkspaceListPage.vue'),
  },
  // ── Workspace-scoped pages ──
  {
    path: '/workspace/:workspaceId/rules',
    name: 'workspace-rules',
    component: () => import('../pages/RulesOverviewPage.vue'),
  },
  {
    path: '/workspace/:workspaceId/compute',
    name: 'workspace-compute',
    component: () => import('../pages/ComputePrepPage.vue'),
  },
  {
    path: '/workspace/:workspaceId/forest',
    name: 'workspace-forest',
    component: () => import('../pages/ForestPage.vue'),
  },
  {
    path: '/workspace/:workspaceId/conflicts',
    name: 'workspace-conflicts',
    component: () => import('../pages/ConflictsPage.vue'),
  },
  // ── Global pages (no workspace context) ──
  {
    path: '/datasource',
    name: 'datasource',
    component: () => import('../pages/DataSourcePage.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../pages/SettingsPage.vue'),
  },
  {
    path: '/rule-editor',
    name: 'rule-editor',
    component: () => import('../pages/RuleEditorPage.vue'),
  },
  {
    path: '/advanced',
    name: 'advanced',
    component: () => import('../pages/AdvancedPage.vue'),
  },
  // ── Legacy redirects ──
  { path: '/rules-overview', redirect: '/' },
  { path: '/forest', redirect: '/' },
  { path: '/compute-prep', redirect: '/' },
  { path: '/conflicts', redirect: '/' },
  { path: '/operations', redirect: '/' },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
