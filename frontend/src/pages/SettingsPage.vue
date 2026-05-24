<template>
  <div class="settings-page gui-page">
    <h2>{{ STR.settingsPage.title }}</h2>

    <el-card shadow="never" style="margin-top: 16px;">

      <el-form label-width="220px" @submit.prevent>
        <div class="section-subtitle">基本设置</div>
        <!-- 备份目录后缀 -->
        <el-form-item label="备份目录名后缀">
          <el-input v-model="form.baksuffix" placeholder="kmmbackup" />
        </el-form-item>

        <!-- 被忽略目录的后缀 -->
        <el-form-item label="被忽略目录的后缀">
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

        <div class="section-subtitle">规则来源</div>

        <!-- 规则来源 -->
        <el-form-item label="规则来源">
          <div style="width: 100%;">
            <div style="margin-bottom: 8px; font-size: 13px; color: #888;">
              规则来源名称 → 路径列表映射，可在弹出窗口中编辑
            </div>
            <el-table :data="ruleSourceEntries" border stripe size="small" style="width: 100%;">
              <el-table-column label="名称" width="200">
                <template #default="{ row }">
                  <code style="font-size: 13px;">{{ row.name }}</code>
                </template>
              </el-table-column>
              <el-table-column label="路径列表" min-width="300">
                <template #default="{ row }">
                  <div style="font-size: 12px; line-height: 1.5;">
                    <div v-for="(p, pi) in row.paths" :key="pi">
                      <code>{{ p }}</code>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ $index }">
                  <el-button size="small" text @click="editRuleSourceEntry($index)">{{ STR.settingsPage.editBtn }}</el-button>
                  <el-popconfirm title="确认删除？" @confirm="removeRuleSourceEntry($index)">
                    <template #reference>
                      <el-button size="small" type="danger" text>{{ STR.settingsPage.deleteBtn }}</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>
            <el-button size="small" type="primary" style="margin-top: 8px;" @click="addRuleSourceEntry">
              ➕ {{ STR.settingsPage.addRuleSource }}
            </el-button>
          </div>
        </el-form-item>

        <!-- 规则来源编辑对话框 -->
        <el-dialog v-model="ruleSourceDialogVisible" :title="ruleSourceDialogTitle" width="600px">
          <el-form>
            <el-form-item :label="STR.settingsPage.ruleSourceName">
              <el-input v-model="ruleSourceDialogName" :placeholder="STR.settingsPage.ruleSourceName" />
            </el-form-item>
            <el-form-item :label="STR.settingsPage.ruleSourcePaths">
              <el-input
                v-model="ruleSourceDialogPaths"
                type="textarea"
                :rows="6"
                :placeholder="STR.settingsPage.ruleSourcePathsPlaceholder"
              />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="ruleSourceDialogVisible = false">{{ STR.settingsPage.cancelBtn }}</el-button>
            <el-button type="primary" @click="confirmRuleSourceDialog">{{ STR.settingsPage.confirmBtn }}</el-button>
          </template>
        </el-dialog>

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
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { apiPost } from '../api/transport'
// workspace localStorage no longer used — backend/config API handles persistence
import { STR } from '../locales/zh-CN'

interface DbEntry {
  key: string
  value: string
}

interface SettingsForm {
  baksuffix: string
  bakignore: string[]
  databases: Array<{ key: string; value: string }>
}

const DEFAULT_DB_PATH = '~/.local/share/kmm/database.json'

// config_index — not shown to user, only passed back for save operations
const configIndex = ref('')

const form = ref<SettingsForm>({
  baksuffix: 'kmmbackup',
  bakignore: [],
  databases: [{ key: 'default', value: DEFAULT_DB_PATH }],
})

const saving = ref(false)

// bakignore add state
const addingBakignore = ref(false)
const newBakignore = ref('')

// ── rule sources object state ──

/** rule_sources as {name: {paths: [...]}} */
const ruleSourcesMap = ref<Record<string, { paths: string[] }>>({})

/** Computed entry list for table display */
const ruleSourceEntries = computed(() => {
  return Object.entries(ruleSourcesMap.value).map(([name, entry]) => ({
    name,
    paths: entry.paths || [],
  }))
})

/** Rule source dialog state */
const ruleSourceDialogVisible = ref(false)
const ruleSourceDialogTitle = ref('')
const ruleSourceDialogIsAdd = ref(true)
const ruleSourceDialogOrigName = ref('')
const ruleSourceDialogName = ref('')
const ruleSourceDialogPaths = ref('')

// bakignore inline edit state
const editingBakignoreIdx = ref(-1)
const editingBakignoreVal = ref('')

onMounted(async () => {
  try {
    const result = await apiPost<Record<string, unknown>>('/config/discover', {})
    if (result.ok && result.data) {
      const data = result.data as Record<string, unknown>
      const uc = data.config as Record<string, unknown>

      // Store config_index for save (not displayed to user)
      configIndex.value = (data.config_index as string) || ''

      form.value.baksuffix = (uc.baksuffix as string) || 'kmmbackup'
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
      // Load rule_sources as {name: {paths: [...]}}
      const rs = uc.rule_sources
      if (rs && typeof rs === 'object' && !Array.isArray(rs)) {
        ruleSourcesMap.value = rs as Record<string, { paths: string[] }>
      }
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
      config_index: configIndex.value,
      config: {
        baksuffix: form.value.baksuffix,
        bakignore: form.value.bakignore,
        databases,
        rule_sources: ruleSourcesMap.value,
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

// ── rule sources dialog management ──

function addRuleSourceEntry() {
  ruleSourceDialogIsAdd.value = true
  ruleSourceDialogTitle.value = STR.settingsPage.addRuleSourceDialogTitle
  ruleSourceDialogOrigName.value = ''
  ruleSourceDialogName.value = ''
  ruleSourceDialogPaths.value = ''
  ruleSourceDialogVisible.value = true
}

function editRuleSourceEntry(idx: number) {
  const entry = ruleSourceEntries.value[idx]
  if (!entry) return
  ruleSourceDialogIsAdd.value = false
  ruleSourceDialogTitle.value = STR.settingsPage.editRuleSourceDialogTitle
  ruleSourceDialogOrigName.value = entry.name
  ruleSourceDialogName.value = entry.name
  ruleSourceDialogPaths.value = entry.paths.join('\n')
  ruleSourceDialogVisible.value = true
}

function confirmRuleSourceDialog() {
  const name = ruleSourceDialogName.value.trim()
  const pathsStr = ruleSourceDialogPaths.value.trim()
  if (!name) {
    ElMessage.warning('名称不能为空')
    return
  }
  const paths = pathsStr
    .split('\n')
    .map((p) => p.trim())
    .filter(Boolean)

  const map = { ...ruleSourcesMap.value }
  if (ruleSourceDialogIsAdd.value) {
    if (map[name]) {
      ElMessage.warning('该名称已存在')
      return
    }
  } else {
    // Editing — handle rename
    if (name !== ruleSourceDialogOrigName.value) {
      delete map[ruleSourceDialogOrigName.value]
    }
  }
  map[name] = { paths }
  ruleSourcesMap.value = map
  ruleSourceDialogVisible.value = false
}

function removeRuleSourceEntry(idx: number) {
  const entry = ruleSourceEntries.value[idx]
  if (entry) {
    const map = { ...ruleSourcesMap.value }
    delete map[entry.name]
    ruleSourcesMap.value = map
  }
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
.settings-page {
  margin: 0 auto;
  padding: 16px 24px;
}
.section-subtitle {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  padding: 8px 0 4px;
  margin-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}
</style>
