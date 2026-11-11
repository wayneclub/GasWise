import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'
import { registerCatalog } from '../i18n'
import { es } from '../i18n/es'
import { ja } from '../i18n/ja'
import { ko } from '../i18n/ko'
import { zhCN } from '../i18n/zh-CN'
import { zhTW } from '../i18n/zh-TW'

registerCatalog('es', es)
registerCatalog('ja', ja)
registerCatalog('ko', ko)
registerCatalog('zh-CN', zhCN)
registerCatalog('zh-TW', zhTW)

configure({ asyncUtilTimeout: 15000 })

beforeEach(() => {
  sessionStorage.clear()
  Object.defineProperty(navigator, 'permissions', { configurable: true, value: undefined })
})

afterEach(() => {
  cleanup()
  Object.defineProperty(navigator, 'permissions', { configurable: true, value: undefined })
})
