<template>
  <div>
    <h2>{{ STR.settingsPage.title }}</h2>

    <el-card shadow="never" style="margin-top: 16px;">
      <el-form label-width="220px" @submit.prevent>
        <!-- 备份目录前缀 -->
        <el-form-item label="备份目录名前缀">
          <el-input v-model="form.bakprefix" placeholder="kmmbackup_" />
        </el-form-item>

        <!-- 备份忽略模式 -->
        <el-form-item label="备份忽略模式">
          <div style="width: 100%;">
            <div style="margin-bottom: 8px;">
              <el-button size="small" @click="onAddBakignore">+ 添加模式</el-button>
              <template v-if="addingBakignore">
                <el-input
                  v-model="newBakignore"
                  placeholder="输入忽略模式"
                  size="small"
                  style="width: 200px; margin-left: 8px;"
                  @keyup.enter="confirmAddBakignore"
                />
                <el-button size="small" type="primary" style="margin-left: 4px;" @click="confirmAddBakignore">
                  确定
                </el-button>
                <el-button size="small" @click="cancelAddBakignore">
                  取消
                </el-button>
              </template>
            </div>
            <div
              v-if="form.bakignore.length > 0"
              style="border: 1px solid #dcdfe6; border-radius: 4px; padding: 4px 8px;"
            >
              <div
                v-for="(item, idx) in form.bakignore"
                :key="idx"
                style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;"
              >
                <span style="font-family: monospace; font-size: 13px;">{{ item }}</span>
                <el-button size="small" type="danger" text @click="removeBakignore(idx)">删除</el-button>
              </div>
            </div>
          </div>
        </el-form-item>

        <!-- Database 输出路径 -->
        <el-form-item label="Database 输出路径">
          <el-input v-model="form.databaseOutputPath" placeholder="/tmp/modmanager_database_generated.json" />
        </el-form-item>

        <!-- Aggregated Rules 输出路径 -->
        <el-form-item label="Aggregated Rules 输出路径">
          <el-input v-model="form.aggregatedOutputPath" placeholder="/tmp/aggregated_rule_set.json" />
        </el-form-item>

        <el-divider content-position="left">规则来源</el-divider>

        <!-- 规则来源 -->
        <el-form-item label="规则来源">
          <div style="width: 100%;">
            <div style="margin-bottom: 8px; font-size: 13px; color: #888;">
              目录以 / 结尾，或以 .kmmrule.json 结尾的文件
            </div>
            <div
              v-if="form.ruleSources.length > 0"
              style="border: 1px solid #dcdfe6; border-radius: 4px; padding: 4px 8px; margin-bottom: 8px;"
            >
              <div
                v-for="(item, idx) in form.ruleSources"
                :key="idx"
                style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;"
              >
                <span style="font-family: monospace; font-size: 13px;">{{ item }}</span>
                <el-button size="small" type="danger" text @click="removeRuleSource(idx)">删除</el-button>
              </div>
            </div>
            <div style="display: flex; align-items: center;">
              <el-input
                v-model="newRuleSource"
                placeholder="添加来源"
                size="small"
                style="width: 300px;"
                @keyup.enter="confirmAddRuleSource"
              />
              <el-button size="small" type="primary" style="margin-left: 8px;" @click="confirmAddRuleSource">
                添加
              </el-button>
            </div>
          </div>
        </el-form-item>

        <!-- 保存按钮 -->
        <el-form-item>
          <el-button type="primary" @click="onSaveConfig" :loading="saving">
            {{ STR.settingsPage.saveBtn }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { apiPost } from '../api/client'
import { STR } from '../locales/zh-CN'

interface SettingsForm {
  bakprefix: string
  bakignore: string[]
  databaseOutputPath: string
  aggregatedOutputPath: string
  ruleSources: string[]
}

const form = ref<SettingsForm>({
  bakprefix: 'kmmbackup_',
  bakignore: [],
  databaseOutputPath: '',
  aggregatedOutputPath: '',
  ruleSources: [],
})

const saving = ref(false)

// bakignore add state
const addingBakignore = ref(false)
const newBakignore = ref('')

// rule source add state
const newRuleSource = ref('')

onMounted(async () => {
  try {
    const result = await apiPost<{ user_config: Record<string, unknown> }>('/api/config/discover', {})
    if (result.ok && result.data) {
      const uc = result.data.user_config || {}
      form.value.bakprefix = (uc.bakprefix as string) || 'kmmbackup_'
      form.value.bakignore = (uc.bakignore as string[]) || []
      form.value.databaseOutputPath = (uc.database_output_path as string) || ''
      form.value.aggregatedOutputPath = (uc.aggregated_ruleset_output_path as string) || ''
      form.value.ruleSources = (uc.rule_sources as string[]) || []
    }
  } catch {
    // 加载失败忽略
  }
})

async function onSaveConfig() {
  saving.value = true
  try {
    const result = await apiPost('/api/config/save', {
      output_path: null,
      config: {
        bakprefix: form.value.bakprefix,
        bakignore: form.value.bakignore,
        database_output_path: form.value.databaseOutputPath || null,
        aggregated_ruleset_output_path: form.value.aggregatedOutputPath || null,
        rule_sources: form.value.ruleSources,
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

// ── bakignore management ──

function onAddBakignore() {
  addingBakignore.value = true
  newBakignore.value = ''
}

function confirmAddBakignore() {
  const val = newBakignore.value.trim()
  if (val) {
    form.value.bakignore.push(val)
  }
  addingBakignore.value = false
  newBakignore.value = ''
}

function cancelAddBakignore() {
  addingBakignore.value = false
  newBakignore.value = ''
}

function removeBakignore(idx: number) {
  form.value.bakignore.splice(idx, 1)
}

// ── rule sources management ──

function confirmAddRuleSource() {
  const val = newRuleSource.value.trim()
  if (val) {
    form.value.ruleSources.push(val)
  }
  newRuleSource.value = ''
}

function removeRuleSource(idx: number) {
  form.value.ruleSources.splice(idx, 1)
}
</script>
