<template>
  <div>
    <h2>备份管理</h2>
    <el-card shadow="never" style="margin-bottom: 16px;">
      <el-form :model="form" label-width="120px">
        <el-form-item label="备份目录">
          <el-input v-model="form.backupDir" placeholder="输入备份目录路径" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onScan">扫描备份</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table v-if="backupDirs.length > 0" :data="backupDirs">
      <el-table-column prop="path" label="备份目录" />
      <el-table-column prop="fileCount" label="文件数" />
      <el-table-column label="操作">
        <template #default="{ row }">
          <el-button size="small" type="danger" @click="restore(row.path)">恢复</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-else description="尚未扫描备份目录" />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'

interface BackupDir {
  path: string
  fileCount: number
}

const form = reactive({
  backupDir: '',
})

const backupDirs = ref<BackupDir[]>([])

async function onScan() {
  // MVP: placeholder — in future this will call an API endpoint
  backupDirs.value = []
}

async function restore(path: string) {
  // MVP: placeholder
}
</script>
