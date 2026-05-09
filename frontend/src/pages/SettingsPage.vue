<template>
  <div>
    <h2>{{ STR.settingsPage.title }}</h2>
    <el-card shadow="never" style="margin-top: 16px;">
      <el-form label-width="220px" @submit.prevent>
        <el-form-item label="备份目录名前缀">
          <el-input v-model="form.bakprefix" placeholder="kmmbackup_" />
        </el-form-item>
        <el-form-item label="数据库路径">
          <el-input v-model="form.databaseOutputPath" placeholder="~/.local/share/kmm/database.json" />
        </el-form-item>
        <el-form-item label="聚合规则集输出路径">
          <el-input v-model="form.aggregatedOutputPath" placeholder="~/.local/share/kmm/aggregated_rule_set.json" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSaveConfig" :loading="saving">
            {{ STR.settingsPage.saveBtn }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Database JSON（高级，默认折叠） -->
    <el-card shadow="never" style="margin-top: 16px;">
      <el-collapse>
        <el-collapse-item :title="STR.settingsPage.databaseJsonAdvanced">
          <el-input
            type="textarea"
            :rows="12"
            v-model="databaseJsonText"
            placeholder="Database JSON 内容..."
          />
          <el-button
            type="success"
            style="margin-top: 8px;"
            @click="onSaveDatabaseJson"
            :loading="savingDb"
          >
            💾 保存到后端
          </el-button>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { apiPost } from '../api/client'
import { useDataSourceStore } from '../stores/datasource'
import { STR } from '../locales/zh-CN'

const dsStore = useDataSourceStore()

const form = ref({
  bakprefix: 'kmmbackup_',
  databaseOutputPath: '',
  aggregatedOutputPath: '',
})
const saving = ref(false)

// Database JSON（从 datasource store 重建）
const databaseJsonText = computed({
  get: () => {
    const db = {
      steamlib: dsStore.libraries.map(l => ({
        path: l.path,
        game: dsStore.games.filter(g => g.libraryIndex === l.index).map(g => g.appid),
      })),
      game: dsStore.games.map(g => ({
        appid: g.appid,
        name: g.name,
        basepath: g.basepath,
        modpath: g.modpath,
        mods_found: [],
        managed: g.managed,
      })),
      mod: dsStore.mods.map(m => ({
        mixed_id: `${m.appid}:${m.modid}`,
        path: m.path,
        managed: m.managed,
      })),
      warnings: dsStore.warnings,
      errors: dsStore.errors,
      history: [],
    }
    return JSON.stringify(db, null, 2)
  },
  set: () => {},
})
const savingDb = ref(false)

onMounted(async () => {
  try {
    const result = await apiPost<Record<string, unknown>>('/api/config/discover', {})
    if (result.ok && result.data) {
      form.value.bakprefix = (result.data.bakprefix as string) || 'kmmbackup_'
      form.value.databaseOutputPath = (result.data.database_output_path as string) || ''
      form.value.aggregatedOutputPath = (result.data.aggregated_ruleset_output_path as string) || ''
    }
  } catch { /* 加载失败忽略 */ }
})

async function onSaveConfig() {
  saving.value = true
  try {
    const result = await apiPost('/api/config/save', {
      output_path: null,
      config: {
        bakprefix: form.value.bakprefix,
        database_output_path: form.value.databaseOutputPath || null,
        aggregated_ruleset_output_path: form.value.aggregatedOutputPath || null,
      },
    })
    if (result.ok) {
      ElMessage.success('设置已保存')
    } else {
      ElMessage.error(result.errors?.[0] || '保存失败')
    }
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function onSaveDatabaseJson() {
  savingDb.value = true
  try {
    const db = JSON.parse(databaseJsonText.value)
    const result = await apiPost('/api/database/save', {
      database: db,
    })
    if (result.ok) {
      ElMessage.success('Database JSON 已同步到后端')
    } else {
      ElMessage.error(result.errors?.[0] || '同步失败')
    }
  } catch (e) {
    ElMessage.error('JSON 格式错误')
  } finally {
    savingDb.value = false
  }
}
</script>
