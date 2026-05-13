<template>
  <div>
    <h2>{{ STR.settingsPage.title }}</h2>

    <el-card shadow="never" style="margin-top: 16px;">
      <!-- 首次使用提示 -->
      <el-alert
        v-if="!form.userConfigPath"
        title="首次使用"
        type="info"
        show-icon
        :closable="false"
        style="margin-bottom: 16px;"
      >
        <template #default>
          请填写必要的配置信息后保存
        </template>
      </el-alert>

      <el-form label-width="220px" @submit.prevent>
        <div class="section-subtitle">基本设置</div>
        <!-- 备份目录前缀 -->
        <el-form-item label="备份目录名前缀">
          <el-input v-model="form.bakprefix" placeholder="kmmbackup_" />
        </el-form-item>

        <!-- 备份忽略模式 -->
        <el-form-item label="备份忽略模式">
          <div style="width: 100%;">
            <div
              v-if="form.bakignore.length > 0 || addingBakignore"
              style="border: 1px solid #dcdfe6; border-radius: 4px; padding: 4px 8px; margin-bottom: 8px;"
            >
              <div
                v-for="(item, idx) in form.bakignore"
                :key="idx"
                style="display: flex; align-items: center; min-height: 32px; margin-bottom: 4px;"
              >
                <!-- 显示态 -->
                <template v-if="editingBakignoreIdx !== idx">
                  <code
                    style="flex: 1; font-size: 13px; cursor: pointer;"
                    @click="startEditBakignore(idx, item)"
                  >{{ item }}</code>
                  <el-popconfirm title="确认删除？" @confirm="removeBakignore(idx)">
                    <template #reference>
                      <el-button size="small" type="danger" text>删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
                <!-- 编辑态 -->
                <template v-else>
                  <el-input
                    v-model="editingBakignoreVal"
                    size="small"
                    style="flex: 1; margin-right: 4px;"
                    @keyup.enter="confirmEditBakignore(idx)"
                    @keyup.esc="cancelEditBakignore"
                  />
                  <el-button size="small" type="primary" style="margin-left: 4px;" @click="confirmEditBakignore(idx)">确定</el-button>
                  <el-button size="small" @click="cancelEditBakignore">取消</el-button>
                </template>
              </div>
              <!-- 添加行 -->
              <div style="display: flex; align-items: center; min-height: 32px;">
                <template v-if="!addingBakignore">
                  <span
                    style="cursor: pointer; font-size: 13px; color: #409eff;"
                    @click="onAddBakignore"
                  >➕ 添加模式</span>
                </template>
                <template v-else>
                  <el-input
                    v-model="newBakignore"
                    placeholder="输入忽略模式"
                    size="small"
                    style="flex: 1; margin-right: 4px;"
                    @keyup.enter="confirmAddBakignore"
                    @keyup.esc="cancelAddBakignore"
                  />
                  <el-button size="small" type="primary" style="margin-left: 4px;" @click="confirmAddBakignore">确定</el-button>
                  <el-button size="small" @click="cancelAddBakignore">取消</el-button>
                </template>
              </div>
            </div>
            <div v-else>
              <span
                style="cursor: pointer; font-size: 13px; color: #409eff;"
                @click="onAddBakignore"
              >➕ 添加模式</span>
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

        <!-- User Config 路径 -->
        <el-form-item label="用户配置文件路径">
          <el-input v-model="form.userConfigPath" placeholder="~/.local/share/kmm/user_config.json" />
        </el-form-item>

        <div class="section-subtitle">规则来源</div>

        <!-- 规则来源 -->
        <el-form-item label="规则来源">
          <div style="width: 100%;">
            <div style="margin-bottom: 8px; font-size: 13px; color: #888;">
              填写目录：自动扫描目录中 <code>.kmmrule.json</code> 文件；填写文件名：单独登记该文件
            </div>
            <div
              v-if="form.ruleSources.length > 0 || isAddingRuleSource"
              style="border: 1px solid #dcdfe6; border-radius: 4px; padding: 4px 8px; margin-bottom: 8px;"
            >
              <div
                v-for="(item, idx) in form.ruleSources"
                :key="idx"
                style="display: flex; align-items: center; min-height: 32px; margin-bottom: 4px;"
              >
                <!-- 显示态 -->
                <template v-if="editingRuleSourceIdx !== idx">
                  <code
                    style="flex: 1; font-size: 13px; cursor: pointer;"
                    @click="startEditRuleSource(idx, item)"
                  >{{ item }}</code>
                  <el-popconfirm title="确认删除？" @confirm="removeRuleSource(idx)">
                    <template #reference>
                      <el-button size="small" type="danger" text>删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
                <!-- 编辑态 -->
                <template v-else>
                  <el-input
                    v-model="editingRuleSourceVal"
                    size="small"
                    style="flex: 1; margin-right: 4px;"
                    @keyup.enter="confirmEditRuleSource(idx)"
                    @keyup.esc="cancelEditRuleSource"
                  />
                  <el-button size="small" type="primary" style="margin-left: 4px;" @click="confirmEditRuleSource(idx)">确定</el-button>
                  <el-button size="small" @click="cancelEditRuleSource">取消</el-button>
                </template>
              </div>
              <!-- 添加行 -->
              <div style="display: flex; align-items: center; min-height: 32px;">
                <template v-if="!isAddingRuleSource">
                  <span
                    style="cursor: pointer; font-size: 13px; color: #409eff;"
                    @click="isAddingRuleSource = true"
                  >➕ 添加来源</span>
                </template>
                <template v-else>
                  <el-input
                    v-model="newRuleSource"
                    placeholder="添加来源"
                    size="small"
                    style="flex: 1; margin-right: 4px;"
                    @keyup.enter="confirmAddRuleSource"
                    @keyup.esc="cancelAddRuleSource"
                  />
                  <el-button size="small" type="primary" style="margin-left: 4px;" @click="confirmAddRuleSource">确定</el-button>
                  <el-button size="small" @click="cancelAddRuleSource">取消</el-button>
                </template>
              </div>
            </div>
            <div v-else>
              <span
                style="cursor: pointer; font-size: 13px; color: #409eff;"
                @click="isAddingRuleSource = true"
              >➕ 添加来源</span>
            </div>
          </div>
        </el-form-item>

        <!-- 保存按钮 -->
        <el-form-item>
          <el-button type="primary" size="small" @click="onSaveConfig" :loading="saving">
            {{ STR.settingsPage.saveBtn }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { apiPost } from '../api/client'
import { STR } from '../locales/zh-CN'

interface SettingsForm {
  bakprefix: string
  bakignore: string[]
  databaseOutputPath: string
  aggregatedOutputPath: string
  userConfigPath: string
  ruleSources: string[]
}

const form = ref<SettingsForm>({
  bakprefix: 'kmmbackup_',
  bakignore: [],
  databaseOutputPath: '',
  aggregatedOutputPath: '',
  userConfigPath: '',
  ruleSources: [],
})

const saving = ref(false)

// bakignore add state
const addingBakignore = ref(false)
const newBakignore = ref('')

// rule source add state
const newRuleSource = ref('')

// rule sources inline edit state
const editingRuleSourceIdx = ref(-1)
const editingRuleSourceVal = ref('')
const isAddingRuleSource = ref(false)

// bakignore inline edit state
const editingBakignoreIdx = ref(-1)
const editingBakignoreVal = ref('')

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
      form.value.userConfigPath = (uc.user_config_path as string) || ''
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
        user_config_path: form.value.userConfigPath || null,
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
  isAddingRuleSource.value = false
}

function cancelAddRuleSource() {
  isAddingRuleSource.value = false
  newRuleSource.value = ''
}

// ── rule sources inline edit ──

function startEditRuleSource(idx: number, val: string) {
  if (editingRuleSourceIdx.value !== -1) cancelEditRuleSource()
  if (isAddingRuleSource.value) cancelAddRuleSource()
  editingRuleSourceIdx.value = idx
  editingRuleSourceVal.value = val
}

function confirmEditRuleSource(idx: number) {
  const val = editingRuleSourceVal.value.trim()
  if (val) {
    form.value.ruleSources[idx] = val
  }
  editingRuleSourceIdx.value = -1
  editingRuleSourceVal.value = ''
}

function cancelEditRuleSource() {
  editingRuleSourceIdx.value = -1
  editingRuleSourceVal.value = ''
}

// ── bakignore inline edit ──

function startEditBakignore(idx: number, val: string) {
  if (editingBakignoreIdx.value !== -1) cancelEditBakignore()
  if (addingBakignore.value) cancelAddBakignore()
  editingBakignoreIdx.value = idx
  editingBakignoreVal.value = val
}

function confirmEditBakignore(idx: number) {
  const val = editingBakignoreVal.value.trim()
  if (val) {
    form.value.bakignore[idx] = val
  }
  editingBakignoreIdx.value = -1
  editingBakignoreVal.value = ''
}

function cancelEditBakignore() {
  editingBakignoreIdx.value = -1
  editingBakignoreVal.value = ''
}

function removeRuleSource(idx: number) {
  form.value.ruleSources.splice(idx, 1)
}
</script>

<style scoped>
.section-subtitle {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  padding: 8px 0 4px;
  margin-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}
</style>
