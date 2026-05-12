import { databaseHandlers } from './database'
import { pipelineHandlers } from './pipeline'
import { configHandlers } from './config'
import { rulesHandlers } from './rules'
import { backupsHandlers } from './backups'
import { workspaceHandlers } from './workspace'

export const handlers = [
  ...databaseHandlers,
  ...pipelineHandlers,
  ...configHandlers,
  ...rulesHandlers,
  ...backupsHandlers,
  ...workspaceHandlers,
]
