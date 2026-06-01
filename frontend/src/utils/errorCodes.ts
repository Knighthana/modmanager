import { STR } from '../locales/zh-CN'

export const WARNING_DESCRIPTIONS: Record<string, string> = {
    'W_LOCAL_MOD_MISSING': STR.errorCodes.W_LOCAL_MOD_MISSING,
    'W_NO_SOURCE_MATCH': STR.errorCodes.W_NO_SOURCE_MATCH,
    'W_MISSING_SOURCE_ROOT': STR.errorCodes.W_MISSING_SOURCE_ROOT,
    'W_MISSING_DEST_ROOT': STR.errorCodes.W_MISSING_DEST_ROOT,
    'W_CREATE_TARGET_EXISTS_OVERWRITE': STR.errorCodes.W_CREATE_TARGET_EXISTS_OVERWRITE,
    'W_FOREST_BRANCHING': STR.errorCodes.W_FOREST_BRANCHING,
    'W_SOURCE_DELETED': STR.errorCodes.W_SOURCE_DELETED,
    'W_SOURCE_DIRECTORY_DELETED': STR.errorCodes.W_SOURCE_DIRECTORY_DELETED,
    'W_EMPTY_ACTIONLIST_AFTER_FILTER': STR.errorCodes.W_EMPTY_ACTIONLIST_AFTER_FILTER,
};

export const ERROR_DESCRIPTIONS: Record<string, string> = {
    'E_DATABASE_INVALID': STR.errorCodes.E_DATABASE_INVALID,
    'E_AGGREGATED_RULE_SET_INVALID': STR.errorCodes.E_AGGREGATED_RULE_SET_INVALID,
    'E_FILE_CIRCULAR_DEP': STR.errorCodes.E_FILE_CIRCULAR_DEP,
    'E_BRANCH_DECISION_INVALID': STR.errorCodes.E_BRANCH_DECISION_INVALID,
    'E_BACKUP_DIR_MISSING': STR.errorCodes.E_BACKUP_DIR_MISSING,
    'E_BACKUP_INFO_MISSING': STR.errorCodes.E_BACKUP_INFO_MISSING,
    'E_BACKUP_TREE_INCOMPLETE': STR.errorCodes.E_BACKUP_TREE_INCOMPLETE,
    'E_BACKUP_TREE_MISSING': STR.errorCodes.E_BACKUP_TREE_MISSING,
    'E_TREE_CONFLICT': STR.errorCodes.E_TREE_CONFLICT,
    'E_ENTITY_CONFLICT': STR.errorCodes.E_ENTITY_CONFLICT,
    'E_TREE_CONFLICT_TARGET_DRIFT': STR.errorCodes.E_TREE_CONFLICT_TARGET_DRIFT,
    'E_DUPLICATE_APPID': STR.errorCodes.E_DUPLICATE_APPID,
    'E_DUPLICATE_MIXED_ID': STR.errorCodes.E_DUPLICATE_MIXED_ID,
    // Aggregator
    'E_KMM_RULE_LOAD_FAILED': STR.errorCodes.E_KMM_RULE_LOAD_FAILED,
    'E_KMM_RULE_INVALID': STR.errorCodes.E_KMM_RULE_INVALID,
    'E_PERMISSION_DENIED_BASE': STR.errorCodes.E_PERMISSION_DENIED_BASE,
    'E_PERMISSION_DENIED_SUB': STR.errorCodes.E_PERMISSION_DENIED_SUB,
    'E_OUTPUT_WRITE_FAILED': STR.errorCodes.E_OUTPUT_WRITE_FAILED,
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
