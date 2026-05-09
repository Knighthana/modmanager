<template>
  <div>
    <h2>设置</h2>
    <el-card shadow="never" style="margin-top: 16px;">
      <el-form label-width="220px">
        <el-form-item label="备份目录名前缀 (bakprefix)">
          <el-input value="kmmbackup_" disabled />
        </el-form-item>
        <el-form-item label="database.json 输出路径">
          <el-input placeholder="~/.local/share/kmm/database.json" disabled />
        </el-form-item>
        <el-form-item label="aggregated_rule_set.json 输出路径">
          <el-input placeholder="~/.local/share/kmm/aggregated_rule_set.json" disabled />
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false" show-icon style="margin-top: 12px;">
        设置页将管理 user_config.json。功能开发中。
      </el-alert>
    </el-card>
  </div>
</template>

<script setup lang="ts">
// SettingsPage — 设置（mock）
// 管理 user_config.json: bakprefix, bakignore, database_output_path, aggregated_ruleset_output_path
</script>
