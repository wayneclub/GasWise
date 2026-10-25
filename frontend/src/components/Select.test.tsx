import { act, fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { Select, type SelectOption } from './Select'

const options: SelectOption<string>[] = [
  { value: 'en', label: 'English', icon: '🇺🇸' },
  { value: 'es', label: 'Español', disabled: true },
  { value: 'ja', label: '日本語', description: 'Japanese' },
]

it('renders a compact accessible trigger without a native select; choosing closes and returns focus', () => {
  const onChange = vi.fn()
  const { container } = render(<Select label="Language" value="en" options={options} onChange={onChange} iconOnly triggerIcon={<svg data-testid="globe" />} />)
  const trigger = screen.getByRole('button', { name: 'Language' })
  expect(trigger).toHaveAccessibleDescription('English')
  expect(container.querySelector('select')).toBeNull()
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  fireEvent.click(trigger)
  expect(screen.getByRole('option', { name: 'English' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('option', { name: 'English' })).toHaveFocus()
  expect(screen.getByRole('option', { name: '日本語' })).toHaveAccessibleDescription('Japanese')
  fireEvent.click(screen.getByRole('option', { name: '日本語' }))
  expect(onChange).toHaveBeenCalledWith('ja')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})

it('supports arrows, Home/End and Escape, skipping disabled options', () => {
  const onChange = vi.fn()
  render(<Select label="Language" value="en" options={options} onChange={onChange} />)
  const trigger = screen.getByRole('button', { name: 'Language' })
  fireEvent.keyDown(trigger, { key: 'ArrowDown' })
  const list = screen.getByRole('listbox')
  fireEvent.keyDown(list, { key: 'ArrowDown' })
  expect(screen.getByRole('option', { name: '日本語' })).toHaveFocus()
  fireEvent.keyDown(list, { key: 'Home' })
  expect(screen.getByRole('option', { name: 'English' })).toHaveFocus()
  fireEvent.keyDown(list, { key: 'End' })
  expect(screen.getByRole('option', { name: '日本語' })).toHaveFocus()
  fireEvent.keyDown(list, { key: 'Escape' })
  expect(trigger).toHaveFocus()
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
  expect(onChange).not.toHaveBeenCalled()
})

it.each(['Enter', ' '])('confirms the focused option with %j and returns focus', key => {
  const onChange = vi.fn()
  render(<Select label="Language" value="en" options={options} onChange={onChange} />)
  const trigger = screen.getByRole('button', { name: 'Language' })
  fireEvent.click(trigger)
  fireEvent.keyDown(screen.getByRole('listbox'), { key: 'End' })
  fireEvent.keyDown(screen.getByRole('option', { name: '日本語' }), { key })
  expect(onChange).toHaveBeenCalledExactlyOnceWith('ja')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})

it('dismisses outside, on Tab, and when focus leaves without changing the value', () => {
  const onChange = vi.fn()
  render(<><Select label="Language" value="en" options={options} onChange={onChange} /><button>Next</button></>)
  const trigger = screen.getByRole('button', { name: 'Language' })
  fireEvent.click(trigger)
  fireEvent.pointerDown(document.body)
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  fireEvent.click(trigger)
  fireEvent.keyDown(screen.getByRole('listbox'), { key: 'Tab' })
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  fireEvent.click(trigger)
  act(() => screen.getByRole('button', { name: 'Next' }).focus())
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
  expect(onChange).not.toHaveBeenCalled()
})

it('clamps the popup to a narrow viewport and flips above a trigger near the bottom', () => {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ x: 270, y: 720, width: 44, height: 44, top: 720, right: 314, bottom: 764, left: 270, toJSON: () => ({}) })
  vi.stubGlobal('innerWidth', 320)
  vi.stubGlobal('innerHeight', 800)
  const scrollHeight = vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockReturnValue(360)
  render(<Select label="Language" value="en" options={options} onChange={vi.fn()} panelWidth={400} align="end" />)
  fireEvent.click(screen.getByRole('button', { name: 'Language' }))
  expect(screen.getByRole('listbox')).toHaveStyle({ left: '12px', width: '296px', bottom: '88px', maxHeight: '360px' })
  scrollHeight.mockRestore(); vi.restoreAllMocks(); vi.unstubAllGlobals()
})

it('supports custom value and option rendering, classes and disabled triggers', () => {
  const { rerender } = render(<Select label="Choice" value="en" options={options} onChange={vi.fn()} disabled />)
  expect(screen.getByRole('button', { name: 'Choice' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Choice' }))
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  rerender(<Select label="Choice" value="en" options={options} onChange={vi.fn()} panelClassName="custom-panel" optionClassName="custom-option" renderValue={option => `Value: ${option.label}`} renderOption={option => `Choose ${option.label}`} />)
  expect(screen.getByRole('button', { name: 'Choice' })).toHaveTextContent('Value: English')
  fireEvent.click(screen.getByRole('button', { name: 'Choice' }))
  expect(screen.getByRole('listbox')).toHaveClass('custom-panel')
  expect(screen.getByRole('option', { name: 'English' })).toHaveClass('custom-option')
  expect(screen.getByRole('option', { name: 'English' })).toHaveTextContent('Choose English')
})

it('waits until the positioned popup is visible before focusing the selected option', () => {
  const originalFocus = HTMLElement.prototype.focus
  const focus = vi.spyOn(HTMLElement.prototype, 'focus').mockImplementation(function (this: HTMLElement, options?: FocusOptions) {
    if (this.closest<HTMLElement>('[role="listbox"]')?.style.visibility === 'hidden') return
    originalFocus.call(this, options)
  })
  render(<Select label="Language" value="en" options={options} onChange={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'Language' }))
  expect(screen.getByRole('option', { name: 'English' })).toHaveFocus()
  focus.mockRestore()
})

it('supports typeahead and unique IDs for independently reused instances', () => {
  render(<><Select label="First" value="ja" options={options} onChange={vi.fn()} /><Select label="Second" value="en" options={options} onChange={vi.fn()} /></>)
  const first = screen.getByRole('button', { name: 'First' })
  const second = screen.getByRole('button', { name: 'Second' })
  expect(first.getAttribute('aria-describedby')).not.toBe(second.getAttribute('aria-describedby'))
  fireEvent.click(first)
  fireEvent.keyDown(screen.getByRole('listbox'), { key: 'e' })
  expect(screen.getByRole('option', { name: 'English' })).toHaveFocus()
  fireEvent.pointerDown(second)
  fireEvent.click(second)
  expect(first).toHaveAttribute('aria-expanded', 'false')
  expect(second).toHaveAttribute('aria-expanded', 'true')
})

it('focuses a selected empty-string value, which is a valid reusable option', () => {
  render(<Select label="Filter" value="" options={[{ value: '', label: 'All stations' }, ...options]} onChange={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'Filter' }))
  expect(screen.getByRole('option', { name: 'All stations' })).toHaveFocus()
})

it('does not reopen an old popup when a disabled control becomes available again', () => {
  const props = { label: 'Language', value: 'en', options, onChange: vi.fn() }
  const { rerender } = render(<Select {...props} />)
  fireEvent.click(screen.getByRole('button', { name: 'Language' }))
  rerender(<Select {...props} disabled />)
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  rerender(<Select {...props} />)
  expect(screen.getByRole('button', { name: 'Language' })).toHaveAttribute('aria-expanded', 'false')
})
