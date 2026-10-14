import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CopyAddress } from './CopyAddress'

const address = '1205 S Alvarado St, Los Angeles, CA 90006-4119'
const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
afterEach(() => {
  vi.restoreAllMocks(); vi.useRealTimers()
  if (originalClipboard) Object.defineProperty(navigator, 'clipboard', originalClipboard)
  else Reflect.deleteProperty(navigator, 'clipboard')
})
function clipboard(writeText = vi.fn().mockResolvedValue(undefined)) {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  return writeText
}

it('copies the complete address even when the displayed address is abbreviated', async () => {
  const write = clipboard()
  render(<CopyAddress address={address} display="1205 S Alvarado St" />)
  fireEvent.click(screen.getByRole('button', { name: `Copy address: ${address}` }))
  expect(await screen.findByText('Address copied')).toBeInTheDocument()
  expect(write).toHaveBeenCalledExactlyOnceWith(address)
})

it('shows a selectable full address when clipboard access is denied', async () => {
  clipboard(vi.fn().mockRejectedValue(new Error('Permission denied')))
  render(<CopyAddress address={address} display="1205 S Alvarado St" />)
  fireEvent.click(screen.getByRole('button'))
  expect(await screen.findByText(/Could not copy/)).toBeInTheDocument()
  expect(screen.queryByText('Address copied')).not.toBeInTheDocument()
  expect(screen.getByText(address)).toHaveClass('select-text')
  expect(screen.getByRole('button')).toBeEnabled()
})

it('clears successful feedback and does not show stale feedback after an address change', async () => {
  vi.useFakeTimers()
  clipboard()
  const view = render(<CopyAddress address={address} />)
  await act(async () => { fireEvent.click(screen.getByRole('button')) })
  expect(screen.getByText('Address copied')).toBeInTheDocument()
  act(() => { vi.advanceTimersByTime(2500) })
  expect(screen.queryByText('Address copied')).not.toBeInTheDocument()
  await act(async () => { fireEvent.click(screen.getByRole('button')) })
  view.rerender(<CopyAddress address="Another station address" />)
  expect(screen.queryByText('Address copied')).not.toBeInTheDocument()
  expect(screen.getByRole('button')).toBeEnabled()
})

it('prevents repeat writes while copying and ignores a completion for the previous address', async () => {
  let resolve!: () => void
  const write = clipboard(vi.fn().mockImplementation(() => new Promise<void>(done => { resolve = done })))
  const view = render(<CopyAddress address={address} />)
  fireEvent.click(screen.getByRole('button'))
  expect(screen.getByRole('button')).toBeDisabled()
  view.rerender(<CopyAddress address="Another station address" />)
  await act(async () => { resolve() })
  expect(screen.queryByText('Address copied')).not.toBeInTheDocument()
  expect(write).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('button')).toBeEnabled()
})

it('does not offer copying when an address is missing', () => {
  render(<CopyAddress address="   " />)
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})
