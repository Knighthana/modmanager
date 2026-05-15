<template>
  <el-container style="height: 100vh; overflow: hidden;">
    <el-aside width="200px">
      <div style="padding: 16px 12px; border-bottom: 1px solid var(--el-border-color-light); margin-bottom: 4px;">
        <div style="font-weight: 800; font-size: 14px; line-height: 1.4; word-break: break-word; color: var(--el-text-color-primary);">
          <span v-html="STR.layoutShell.title"></span>
        </div>
      </div>
      <el-menu :default-active="currentRoute" router>
        <el-menu-item index="/">
          <span>📂 工作区</span>
        </el-menu-item>
        <template v-if="workspaceId">
          <el-menu-item :index="`/workspace/${workspaceId}/rules`">
            <span>📋 规则概览</span>
          </el-menu-item>
          <el-menu-item :index="`/workspace/${workspaceId}/compute`">
            <span>🧮 计算准备</span>
          </el-menu-item>
          <el-menu-item :index="`/workspace/${workspaceId}/forest`">
            <span>🌲 森林可视</span>
          </el-menu-item>
          <el-menu-item :index="`/workspace/${workspaceId}/conflicts`">
            <span>⚔️ 冲突裁决</span>
            <el-badge v-if="store.unresolvedCount > 0" :value="store.unresolvedCount" />
          </el-menu-item>
        </template>
        <template v-else>
          <el-menu-item disabled>
            <span style="color: var(--el-text-color-placeholder);">📋 规则概览 — 请先创建工作区</span>
          </el-menu-item>
          <el-menu-item disabled>
            <span style="color: var(--el-text-color-placeholder);">🧮 计算准备 — 请先创建工作区</span>
          </el-menu-item>
          <el-menu-item disabled>
            <span style="color: var(--el-text-color-placeholder);">🌲 森林可视 — 请先创建工作区</span>
          </el-menu-item>
        </template>
        <el-menu-item index="/datasource">
          <span>📡 数据来源</span>
        </el-menu-item>
        <el-menu-item index="/rule-editor">
          <span>✏️ 规则制定</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <span>⚙️ 设置面板</span>
        </el-menu-item>
        <el-menu-item index="/advanced">
          <span>🔧 进阶用户</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-main style="overflow-y: auto;">
        <router-view />
      </el-main>
      <SseStatusBar v-if="store.isRunning" />
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useForestStore } from '../stores/forest'
import SseStatusBar from './SseStatusBar.vue'
import { STR } from '../locales/zh-CN'
import { loadCurrentWorkspaceId } from '../utils/persistence'

const route = useRoute()
const store = useForestStore()

const currentRoute = computed(() => route.path)
const workspaceId = computed(() => {
  // Read from URL param (workspace-scoped pages) or sessionStorage fallback
  const fromRoute = (route.params as Record<string, string>).workspaceId
  if (fromRoute) return fromRoute
  return loadCurrentWorkspaceId()
})
</script>
