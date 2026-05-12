<template>
  <el-container style="height: 100vh; overflow: hidden;">
    <el-aside width="200px">
      <div style="padding: 16px 12px; border-bottom: 1px solid var(--el-border-color-light); margin-bottom: 4px;">
        <div style="font-weight: 800; font-size: 14px; line-height: 1.4; word-break: break-word; color: var(--el-text-color-primary);">
          <span v-html="STR.layoutShell.title"></span>
        </div>
      </div>
      <el-menu :default-active="currentRoute" router>
        <el-menu-item index="/datasource">
          <span>{{ STR.layoutShell.navDatasource }}</span>
        </el-menu-item>
        <el-menu-item index="/rules-overview">
          <span>{{ STR.layoutShell.navRulesOverview }}</span>
        </el-menu-item>
        <el-menu-item index="/compute-prep">
          <span>{{ STR.layoutShell.navComputePrep }}</span>
        </el-menu-item>
        <el-menu-item index="/forest">
          <span>{{ STR.layoutShell.navForest }}</span>
        </el-menu-item>
        <el-menu-item index="/conflicts">
          <span>{{ STR.layoutShell.navConflicts }}</span>
          <el-badge v-if="store.unresolvedCount > 0" :value="store.unresolvedCount" />
        </el-menu-item>
        <el-menu-item index="/operations">
          <span>{{ STR.layoutShell.navOperations }}</span>
        </el-menu-item>
        <el-menu-item index="/rule-editor">
          <span>{{ STR.layoutShell.navRuleEditor }}</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <span>{{ STR.layoutShell.navSettings }}</span>
        </el-menu-item>
        <el-menu-item index="/advanced">
          <span>高级</span>
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

const route = useRoute()
const store = useForestStore()

const currentRoute = computed(() => route.path)
</script>
