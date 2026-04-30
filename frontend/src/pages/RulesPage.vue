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

interface RuleFile {
  name: string
  path: string
}

const form = reactive({
  rulesDir: '',
})

const ruleFiles = ref<RuleFile[]>([])
const dialogVisible = ref(false)
const selectedFile = ref<RuleFile | null>(null)
const fileContent = ref('')

async function onScan() {
  // MVP: placeholder — in future this will call an API endpoint
  // For now, we show a message indicating this is a placeholder
  ruleFiles.value = []
}

async function showContent(row: RuleFile) {
  selectedFile.value = row
  fileContent.value = '// 内容加载中...\n// MVP: API 端点尚未实现'
  dialogVisible.value = true
}
</script>
