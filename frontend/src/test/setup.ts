import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'

configure({ asyncUtilTimeout: 5000 })

beforeEach(() => {
  sessionStorage.clear()
  Object.defineProperty(navigator, 'permissions', { configurable: true, value: undefined })
})

afterEach(() => {
  cleanup()
  Object.defineProperty(navigator, 'permissions', { configurable: true, value: undefined })
})
