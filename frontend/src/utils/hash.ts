/**
 * 简单哈希函数 — 用于检测规则集变更
 * 
 * 用途：
 * - ComputePrepPage 对比当前规则集 vs 上次计算的规则集
 * - 如果哈希不同，提醒用户规则已变更，建议重新计算
 * 
 * 实现：base64 编码（不是密码学哈希，仅用于变更检测）
 */

export function hashRuleSet(rules: Record<string, unknown> | null): string {
  if (!rules) return ''
  try {
    const json = JSON.stringify(rules)
    return btoa(json) // base64 编码
  } catch {
    return ''
  }
}
