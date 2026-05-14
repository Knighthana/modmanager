import { databaseHandlers } from './database'
import { pipelineHandlers } from './pipeline'
import { configHandlers } from './config'
import { rulesHandlers } from './rules'
import { backupsHandlers } from './backups'

export const handlers = [
  ...databaseHandlers,
  ...pipelineHandlers,
  ...configHandlers,
  ...rulesHandlers,
  ...backupsHandlers,
]
