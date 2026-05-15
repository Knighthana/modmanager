<template>
  <div class="gui-page">
    <h2>{{ STR.settingsPage.title }}</h2>

    <el-card shadow="never" style="margin-top: 16px;">
      <!-- 首次使用提示 -->
      <el-alert
        v-if="form.firstUse"
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
            <el-table :data="form.bakignore" border stripe size="small" style="width: 100%;">
              <el-table-column label="路径">
                <template #default="{ row, $index }">
                  <template v-if="editingBakignoreIdx !== $index">
                    <code
                      style="cursor: pointer; font-size: 13px;"
                      @click="startEditBakignore($index, row)"
                    >{{ row }}</code>
                  </template>
                  <template v-else>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <el-input
                        v-model="editingBakignoreVal"
                        size="small"
                        @keyup.enter="confirmEditBakignore($index)"
                        @keyup.esc="cancelEditBakignore"
                      />
                      <el-button size="small" type="primary" @click="confirmEditBakignore($index)">确定</el-button>
                      <el-button size="small" @click="cancelEditBakignore">取消</el-button>
                    </div>
                  </template>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-popconfirm title="确认删除？" @confirm="removeBakignore($index)">
                    <template #reference>
                      <el-button size="small" type="danger" text>删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
              <template #append>
                <div style="padding: 4px 0;">
                  <template v-if="!addingBakignore">
                    <span
                      style="cursor: pointer; font-size: 13px; color: #409eff;"
                      @click="onAddBakignore"
                    >➕ 添加模式</span>
                  </template>
                  <template v-else>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <el-input
                        v-model="newBakignore"
                        placeholder="输入忽略模式"
                        size="small"
                        @keyup.enter="confirmAddBakignore"
                        @keyup.esc="cancelAddBakignore"
                      />
                      <el-button size="small" type="primary" @click="confirmAddBakignore">确定</el-button>
                      <el-button size="small" @click="cancelAddBakignore">取消</el-button>
                    </div>
                  </template>
                </div>
              </template>
            </el-table>
          </div>
        </el-form-item>

        <!-- Databases 对象编辑器 -->
        <el-form-item label="Databases">
          <div style="width: 100%;">
            <div style="margin-bottom: 8px; font-size: 13px; color: #888;">
              Database name → 路径映射
            </div>
            <el-table :data="form.databases" border stripe size="small" style="width: 100%;">
              <el-table-column label="名称" width="200">
                <template #default="{ row, $index }">
                  <template v-if="editingDbKeyIdx !== $index">
                    <code
                      style="cursor: pointer; font-size: 13px;"
                      @click="startEditDbKey($index, row)"
                    >{{ row.key }}</code>
                  </template>
                  <template v-else>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <el-input
                        v-model="editingDbKeyVal"
                        size="small"
                        @keyup.enter="confirmEditDbKey($index)"
                        @keyup.esc="cancelEditDbKey"
                      />
                      <el-button size="small" type="primary" @click="confirmEditDbKey($index)">确定</el-button>
                      <el-button size="small" @click="cancelEditDbKey">取消</el-button>
                    </div>
                  </template>
                </template>
              </el-table-column>
              <el-table-column label="路径" min-width="300">
                <template #default="{ row, $index }">
                  <el-input v-model="row.value" size="small" placeholder="输入文件路径" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-popconfirm title="确认删除？" @confirm="removeDbKey($index)">
                    <template #reference>
                      <el-button size="small" type="danger" text>删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
              <template #append>
                <div style="padding: 4px 0;">
                  <template v-if="!addingDbKey">
                    <span
                      style="cursor: pointer; font-size: 13px; color: #409eff;"
                      @click="onAddDbKey"
                    >➕ 添加 database</span>
                  </template>
                  <template v-else>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <el-input
                        v-model="newDbKey"
                        placeholder="输入 database 名称"
                        size="small"
                        @keyup.enter="confirmAddDbKey"
                        @keyup.esc="cancelAddDbKey"
                      />
                      <el-button size="small" type="primary" @click="confirmAddDbKey">确定</el-button>
                      <el-button size="small" @click="cancelAddDbKey">取消</el-button>
                    </div>
                  </template>
                </div>
              </template>
            </el-table>
            <el-button v-if="form.databases.length === 0" size="small" type="info" style="margin-top: 8px;" @click="restoreDefaultDb">
              恢复默认
            </el-button>
          </div>
        </el-form-item>

        <!-- Aggregated Rules 输出路径 -->
        <el-form-item label="Aggregated Rules 输出路径">
          <el-input v-model="form.aggregatedOutputPath" placeholder="/tmp/aggregated_rule_set.json" />
        </el-form-item>

        <!-- User Config 路径（只读，由系统确定） -->
        <el-form-item label="用户配置文件路径">
          <el-input v-model="form.userConfigPath" readonly placeholder="由系统确定" />
        </el-form-item>

        <div class="section-subtitle">规则来源</div>

        <!-- 规则来源 -->
        <el-form-item label="规则来源">
          <div style="width: 100%;">
            <div style="margin-bottom: 8px; font-size: 13px; color: #888;">
              填写目录：自动扫描目录中 <code>.kmmrule.json</code> 文件；填写文件名：单独登记该文件
            </div>
            <el-table :data="form.ruleSources" border stripe size="small" style="width: 100%;">
              <el-table-column label="路径">
                <template #default="{ row, $index }">
                  <template v-if="editingRuleSourceIdx !== $index">
                    <code
                      style="cursor: pointer; font-size: 13px;"
                      @click="startEditRuleSource($index, row)"
                    >{{ row }}</code>
                  </template>
                  <template v-else>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <el-input
                        v-model="editingRuleSourceVal"
                        size="small"
                        @keyup.enter="confirmEditRuleSource($index)"
                        @keyup.esc="cancelEditRuleSource"
                      />
                      <el-button size="small" type="primary" @click="confirmEditRuleSource($index)">确定</el-button>
                      <el-button size="small" @click="cancelEditRuleSource">取消</el-button>
                    </div>
                  </template>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-popconfirm title="确认删除？" @confirm="removeRuleSource($index)">
                    <template #reference>
                      <el-button size="small" type="danger" text>删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
              <template #append>
                <div style="padding: 4px 0;">
                  <template v-if="!isAddingRuleSource">
                    <span
                      style="cursor: pointer; font-size: 13px; color: #409eff;"
                      @click="isAddingRuleSource = true"
                    >➕ 添加来源</span>
                  </template>
                  <template v-else>
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <el-input
                        v-model="newRuleSource"
                        placeholder="添加来源"
                        size="small"
                        @keyup.enter="confirmAddRuleSource"
                        @keyup.esc="cancelAddRuleSource"
                      />
                      <el-button size="small" type="primary" @click="confirmAddRuleSource">确定</el-button>
                      <el-button size="small" @click="cancelAddRuleSource">取消</el-button>
                    </div>
                  </template>
                </div>
              </template>
            </el-table>
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
import { apiPost } from '../api/transport'
// workspace localStorage no longer used — backend/config API handles persistence
import { STR } from '../locales/zh-CN'

interface DbEntry {
  key: string
  value: string
}

interface SettingsForm {
  bakprefix: string
  bakignore: string[]
  databases: DbEntry[]
  aggregatedOutputPath: string
  userConfigPath: string   // read-only, populated from backend source_path
  ruleSources: string[]
  firstUse: boolean
}

const DEFAULT_DB_PATH = '~/.local/share/kmm/database.json'

const form = ref<SettingsForm>({
  bakprefix: 'kmmbackup_',
  bakignore: [],
  databases: [{ key: 'default', value: DEFAULT_DB_PATH }],
  aggregatedOutputPath: '',
  userConfigPath: '',
  ruleSources: [],
  firstUse: false,
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
    const result = await apiPost<Record<string, unknown>>('/config/discover', {})
    if (result.ok && result.data) {
      const uc = result.data as Record<string, unknown>
      form.value.bakprefix = (uc.bakprefix as string) || 'kmmbackup_'
      form.value.bakignore = (uc.bakignore as string[]) || []
      const dbs = uc.databases as Record<string, { path: string }> | undefined
      if (dbs && typeof dbs === 'object') {
        form.value.databases = Object.entries(dbs).map(([key, entry]) => ({
          key,
          value: (entry && typeof entry === 'object' && typeof entry.path === 'string') ? entry.path : '',
        }))
      }
      // If no databases loaded (first use or empty), ensure default
      if (form.value.databases.length === 0) {
        form.value.databases = [{ key: 'default', value: DEFAULT_DB_PATH }]
      }
      form.value.aggregatedOutputPath = (uc.aggregated_ruleset_output_path as string) || ''
      form.value.ruleSources = (uc.rule_sources as string[]) || []
      form.value.userConfigPath = (uc.source_path as string) || ''
      form.value.firstUse = (uc.first_use as boolean) || false
    }
  } catch {
    // 加载失败忽略
  }
})

async function onSaveConfig() {
  saving.value = true
  try {
    // Build databases object from table entries
    const databases: Record<string, { path: string }> = {}
    for (const entry of form.value.databases) {
      if (entry.key.trim()) {
        databases[entry.key.trim()] = { path: entry.value.trim() }
      }
    }

    const result = await apiPost('/config/save', {
      config: {
        bakprefix: form.value.bakprefix,
        bakignore: form.value.bakignore,
        databases,
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

// ── databases object editor ──

const editingDbKeyIdx = ref(-1)
const editingDbKeyVal = ref('')
const addingDbKey = ref(false)
const newDbKey = ref('')
function onAddDbKey() {
  addingDbKey.value = true
  newDbKey.value = ''
}

function confirmAddDbKey() {
  const val = newDbKey.value.trim()
  if (val && !form.value.databases.some(d => d.key === val)) {
    form.value.databases.push({ key: val, value: '' })
  }
  addingDbKey.value = false
  newDbKey.value = ''
}

function cancelAddDbKey() {
  addingDbKey.value = false
  newDbKey.value = ''
}

function removeDbKey(idx: number) {
  form.value.databases.splice(idx, 1)
}

function restoreDefaultDb() {
  if (!form.value.databases.some(d => d.key === 'default')) {
    form.value.databases.push({ key: 'default', value: DEFAULT_DB_PATH })
  }
}

function startEditDbKey(idx: number, row: DbEntry) {
  if (editingDbKeyIdx.value !== -1) cancelEditDbKey()
  if (addingDbKey.value) cancelAddDbKey()
  editingDbKeyIdx.value = idx
  editingDbKeyVal.value = row.key
}

function confirmEditDbKey(idx: number) {
  const val = editingDbKeyVal.value.trim()
  if (val && !form.value.databases.some((d, i) => d.key === val && i !== idx)) {
    form.value.databases[idx].key = val
  }
  editingDbKeyIdx.value = -1
  editingDbKeyVal.value = ''
}

function cancelEditDbKey() {
  editingDbKeyIdx.value = -1
  editingDbKeyVal.value = ''
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
