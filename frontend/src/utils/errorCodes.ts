export const WARNING_DESCRIPTIONS: Record<string, string> = {
    'W_LOCAL_MOD_MISSING': '本地未安装该 mod，对应映射将被跳过',
    'W_NO_SOURCE_MATCH': 'mod 源文件不存在（可能未安装），对应条目将被跳过',
    'W_MISSING_SOURCE_ROOT': '缺少源目录',
    'W_MISSING_DEST_ROOT': '缺少目标目录',
    'W_CREATE_TARGET_EXISTS_OVERWRITE': '目标文件已存在，将被覆盖',
    'W_FOREST_BRANCHING': '该树有多个候选操作，需要用户裁决',
    'W_SOURCE_DELETED': '操作的源文件已被删除，该操作被跳过',
    'W_SOURCE_DIRECTORY_DELETED': '操作的源目录已被删除，该操作被跳过',
    'W_DUPLICATE_APPID': '同一 appid 在多个库中出现',
};

export const ERROR_DESCRIPTIONS: Record<string, string> = {
    'E_DATABASE_INVALID': '数据库格式无效，缺少必要字段',
    'E_AGGREGATED_RULE_SET_INVALID': '规则集格式无效',
    'E_FILE_CIRCULAR_DEP': '文件级循环依赖',
    'E_BRANCH_DECISION_INVALID': '分支决策无效',
    'E_BACKUP_DIR_MISSING': '备份目录不存在',
    'E_BACKUP_INFO_MISSING': '备份元数据缺失',
    'E_BACKUP_TREE_INCOMPLETE': '备份文件树不完整',
    'E_BACKUP_TREE_MISSING': '备份文件树缺失',
    'E_TREE_CONFLICT': '文件树冲突',
    'E_ENTITY_CONFLICT': '实体文件冲突',
    'E_TREE_CONFLICT_TARGET_DRIFT': '目标文件内容与备份不一致',
};

/** 从错误/警告消息中提取类型代码 */
export function extractCode(message: string): string | null {
    const match = message.match(/^(E_\w+|W_\w+)/);
    return match ? match[1] : null;
}

/** 获取错误/警告的人类可读说明 */
export function getDescription(message: string): string | null {
    const code = extractCode(message);
    if (!code) return null;
    return WARNING_DESCRIPTIONS[code] || ERROR_DESCRIPTIONS[code] || null;
}
