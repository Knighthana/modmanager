import ElementPlus from 'element-plus'
import { config } from '@vue/test-utils'

// 在测试环境中全局注册 Element Plus
config.global.plugins = config.global.plugins || []
config.global.plugins.push(ElementPlus)
