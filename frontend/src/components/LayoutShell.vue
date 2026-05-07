<template>
  <el-container style="height: 100%">
    <el-aside width="200px">
      <div style="padding: 16px 12px; border-bottom: 1px solid var(--el-border-color-light); margin-bottom: 4px;">
        <div style="font-weight: 800; font-size: 14px; line-height: 1.4; word-break: break-word; color: var(--el-text-color-primary);">
          🔧 Knighthana's<br/>Mod Manager
        </div>
      </div>
      <el-menu :default-active="currentRoute" router>
        <el-menu-item index="/data-source">
          <span>📡 数据源</span>
        </el-menu-item>
        <el-menu-item index="/forest">
          <span>📊 Forest 可视化</span>
        </el-menu-item>
        <el-menu-item index="/conflicts">
          <span>⚔️ 冲突裁决</span>
          <el-badge v-if="store.unresolvedCount > 0" :value="store.unresolvedCount" />
        </el-menu-item>
        <el-menu-item index="/rules">
          <span>📋 规则管理</span>
        </el-menu-item>
        <el-menu-item index="/backup">
          <span>🗄️ 备份恢复</span>
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

const route = useRoute()
const store = useForestStore()

const currentRoute = computed(() => route.path)
</script>
