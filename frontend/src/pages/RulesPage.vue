<template>
  <div>
    <h2>规则文件管理</h2>
    <el-card shadow="never" style="margin-bottom: 16px;">
      <el-form :model="form" label-width="120px">
        <el-form-item label="规则目录">
          <el-input v-model="form.rulesDir" placeholder="输入 kmm_rule 文件所在目录路径" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onScan">扫描</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table v-if="ruleFiles.length > 0" :data="ruleFiles" @row-click="showContent">
      <el-table-column prop="name" label="文件名" />
      <el-table-column prop="path" label="路径" />
    </el-table>

    <el-empty v-else description="尚未扫描规则文件" />

    <el-dialog v-model="dialogVisible" :title="selectedFile?.name || ''" width="60%">
      <pre style="max-height: 60vh; overflow: auto; background: #f5f5f5; padding: 12px; border-radius: 4px; font-size: 13px;">{{ fileContent }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { apiPost } from '../api/client'

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
    fileContent.value = resp.errors?.join('\n') || '扫描失败'
    // Use dialog to show errors too
    selectedFile.value = null
  }
}

async function showContent(row: RuleFile) {
  selectedFile.value = row
  fileContent.value = '加载中...'
  dialogVisible.value = true

  const resp = await apiPost('/rules/read', { path: row.path })
  if (resp.ok && resp.data) {
    fileContent.value = (resp.data as { content: string }).content
  } else {
    fileContent.value = resp.errors?.join('\n') || '读取失败'
  }
}
</script>
