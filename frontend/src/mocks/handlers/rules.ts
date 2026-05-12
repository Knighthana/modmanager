import { http, HttpResponse } from 'msw'
import rulesList from '../data/rules-list.json'

// ── Mock affected-entries data ───────────────────────────────────────────
// Structured: 2 libraries, 3 games (1 appid has duplicate), 3 mods (1 mixed_id has duplicate)
const mockAffectedEntries = {
  libraries: [
    { index: 0, path: '/mnt/d/SteamLibrary/steamapps', game_count: 2, mod_count: 3 },
    { index: 1, path: '/mnt/e/SteamLibrary/steamapps', game_count: 1, mod_count: 1 },
  ],
  games: [
    {
      appid: '270150',
      name: 'RWR',
      basepath: '/mnt/d/SteamLibrary/steamapps/common/RWR',
      libraryIndex: 0,
      has_duplicate: true,
    },
    {
      appid: '270150',
      name: 'RWR',
      basepath: '/mnt/e/SteamLibrary/steamapps/common/RWR',
      libraryIndex: 1,
      has_duplicate: true,
    },
    {
      appid: '107410',
      name: 'Arma3',
      basepath: '/mnt/d/SteamLibrary/steamapps/common/Arma3',
      libraryIndex: 0,
      has_duplicate: false,
    },
  ],
  mods: [
    {
      mixed_id: '270150:2606099273',
      nickname: 'Castle',
      path: '/mnt/d/SteamLibrary/steamapps/common/RWR/2606099273',
      libraryIndex: 0,
      gameIndex: 0,
      has_duplicate: true,
    },
    {
      mixed_id: '270150:2606099274',
      nickname: 'Forest',
      path: '/mnt/d/SteamLibrary/steamapps/common/RWR/2606099274',
      libraryIndex: 0,
      gameIndex: 0,
      has_duplicate: false,
    },
    {
      mixed_id: '270150:2606099273',
      nickname: 'Castle',
      path: '/mnt/e/SteamLibrary/steamapps/common/RWR/2606099273',
      libraryIndex: 1,
      gameIndex: 1,
      has_duplicate: true,
    },
  ],
}

// ── Mock kmmrule file content keyed by filename ─────────────────────
const mockKmmRuleContent: Record<string, unknown> = {
  'my_mods.kmmrule.json': {
    schema_namespace: 'kmm',
    schema_version: '1.0',
    rule_meta_tag: {
      rulenamespace: 'kmm',
      rulename: '我的规则集',
      author: [{ nickname: 'knighthana' }],
      description: 'RWR + Arma3 的 MOD 管理规则',
    },
    game: [
      { appid: '270150', modid: ['2606099273', '2606099274', '2606099275'] },
      { appid: '107410', modid: ['2890123456'] },
    ],
    mod: [
      {
        mixed_id: '270150:2606099273',
        nickname: 'Castle',
        preview: ['preview.png', 'thumb.png'],
        readme: ['README.md'],
      },
      {
        mixed_id: '270150:2606099274',
        nickname: 'Forest',
        readme: ['forest_readme.txt'],
      },
      {
        mixed_id: '270150:2606099275',
        nickname: 'River',
        preview: ['river_preview.png'],
      },
      {
        mixed_id: '107410:2890123456',
        nickname: 'Grass',
        readme: ['grass_readme.txt'],
      },
    ],
  },
  'extra.kmmrule.json': {
    schema_namespace: 'kmm',
    schema_version: '1.0',
    rule_meta_tag: {
      rulenamespace: 'extra',
      rulename: 'Extra Rules',
      author: [{ nickname: 'modder' }],
      description: 'Additional mod management rules',
    },
    game: [{ appid: '270150', modid: ['2606099273'] }],
    mod: [
      {
        mixed_id: '270150:2606099273',
        nickname: 'Castle',
        preview: ['extra_preview.png'],
      },
    ],
  },
  'unused.kmmrule.json': {
    schema_namespace: 'kmm',
    schema_version: '1.0',
    rule_meta_tag: {
      rulenamespace: 'legacy',
      rulename: 'Old Rules',
      author: [{ nickname: 'archivist' }],
      description: 'Deprecated rule set — kept for reference',
    },
    game: [{ appid: '270150', modid: [] }],
    mod: [],
  },
}

// ── Handlers ─────────────────────────────────────────────────────────

export const rulesHandlers = [
  // POST /api/rules/scan — 扫描规则文件
  http.post('/api/rules/scan', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: rulesList,
    })
  }),

  // POST /api/rules/read — 读取单个 kmmrule 文件内容
  http.post('/api/rules/read', async ({ request }) => {
    const body = (await request.json()) as { path?: string }
    const filePath = body?.path ?? ''

    // Extract filename from path
    const segments = filePath.split('/')
    const fileName = segments[segments.length - 1]

    const content = mockKmmRuleContent[fileName]
    if (!content) {
      return HttpResponse.json({
        ok: false,
        data: null,
        errors: [`Rule file not found: ${filePath}`],
        warnings: [],
      })
    }

    return HttpResponse.json({
      ok: true,
      data: content,
      errors: [],
      warnings: [],
    })
  }),

  // POST /api/rules/aggregate — 聚合已选规则
  http.post('/api/rules/aggregate', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: {
        aggregated: true,
        rule_count: 2,
        timestamp: new Date().toISOString(),
      },
      errors: [],
      warnings: [],
    })
  }),

  // POST /api/rules/validate — 验证规则文件
  http.post('/api/rules/validate', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: { valid: true, errors: [], warnings: [] },
    })
  }),

  // POST /api/rules/save — 保存规则
  http.post('/api/rules/save', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: { saved: true, timestamp: new Date().toISOString() },
    })
  }),

  // POST /api/rules/affected-entries — 查询受选定规则影响的库/游戏/MOD
  http.post('/api/rules/affected-entries', async ({ request }) => {
    const body = (await request.json()) as { aggregated_rule_path?: string }
    if (!body?.aggregated_rule_path) {
      return HttpResponse.json({
        ok: false,
        data: null,
        errors: ['aggregated_rule_path is required'],
        warnings: [],
      })
    }
    return HttpResponse.json({
      ok: true,
      data: mockAffectedEntries,
      errors: [],
      warnings: [],
    })
  }),
]
