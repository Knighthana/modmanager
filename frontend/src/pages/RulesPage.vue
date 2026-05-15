<template>
  <div>
    <h2>{{ STR.rulesPage.title }}</h2>
    <el-card shadow="never" style="margin-bottom: 16px;">
      <el-form :model="form" label-width="120px">
        <el-form-item :label="STR.rulesPage.rulesDirLabel">
          <el-input v-model="form.rulesDir" :placeholder="STR.rulesPage.rulesDirPlaceholder" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onScan">{{ STR.rulesPage.scanBtn }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table v-if="ruleFiles.length > 0" :data="ruleFiles" @row-click="showContent">
      <el-table-column prop="name" :label="STR.rulesPage.filename" />
      <el-table-column prop="path" :label="STR.rulesPage.path" />
    </el-table>

    <el-empty v-else :description="STR.rulesPage.emptyDescription" />

    <el-dialog v-model="dialogVisible" :title="selectedFile?.name || ''" width="60%">
      <pre style="max-height: 60vh; overflow: auto; background: #f5f5f5; padding: 12px; border-radius: 4px; font-size: 13px;">{{ fileContent }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { apiPost } from '../api/transport'
import { STR } from '../locales/zh-CN'

interface RuleFile {
  name: string
  path: string
  size?: number
}

const form = reactive({
  rulesDir: '',
})

const ruleFiles = ref<RuleFile[]>([])
const dialogVisible = ref(false)
const selectedFile = ref<RuleFile | null>(null)
const fileContent = ref('')

async function onScan() {
  if (!form.rulesDir.trim()) return
  const resp = await apiPost('/rules/scan', { dir: form.rulesDir.trim() })
  if (resp.ok && resp.data) {
    ruleFiles.value = (resp.data as { files: RuleFile[] }).files || []
  } else {
    ruleFiles.value = []
    // Show error via a simple alert-like approach
    fileContent.value = resp.errors?.join('\n') || STR.rulesPage.scanFailed
    // Use dialog to show errors too
    selectedFile.value = null
  }
}

async function showContent(row: RuleFile) {
  selectedFile.value = row
  fileContent.value = STR.rulesPage.loading
  dialogVisible.value = true

  const resp = await apiPost('/rules/read', { path: row.path })
  if (resp.ok && resp.data) {
    fileContent.value = (resp.data as { content: string }).content
  } else {
    fileContent.value = resp.errors?.join('\n') || STR.rulesPage.readFailed
  }
}
</script>
