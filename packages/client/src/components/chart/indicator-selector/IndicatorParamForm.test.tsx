// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { IndicatorParamForm } from './IndicatorParamForm'
import type { IndicatorType } from '@/types/api'

const smaType: IndicatorType = {
  type: 'SMA',
  labelTemplate: 'SMA({period})',
  display: 'overlay',
  outputs: ['value'],
  params: [
    { name: 'period', type: 'int', default: 20, min: 2, max: 500, label: 'Period' },
  ],
}

const macdType: IndicatorType = {
  type: 'MACD',
  labelTemplate: 'MACD({fast_period},{slow_period},{signal_period})',
  display: 'panel',
  outputs: ['macd', 'signal', 'histogram'],
  params: [
    { name: 'fast_period', type: 'int', default: 12, min: 2, max: 200, label: 'Fast Period' },
    { name: 'slow_period', type: 'int', default: 26, min: 2, max: 200, label: 'Slow Period' },
    { name: 'signal_period', type: 'int', default: 9, min: 2, max: 200, label: 'Signal Period' },
  ],
}

describe('IndicatorParamForm', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders one input per ParamSchema with defaults populated', () => {
    render(
      <IndicatorParamForm
        type={smaType}
        submitLabel="Add"
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    )
    const input = screen.getByLabelText('Period') as HTMLInputElement
    expect(input).toBeTruthy()
    expect(input.value).toBe('20')
  })

  it('renders all inputs for MACD with defaults', () => {
    render(
      <IndicatorParamForm
        type={macdType}
        submitLabel="Add"
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    )
    const fast = screen.getByLabelText('Fast Period') as HTMLInputElement
    const slow = screen.getByLabelText('Slow Period') as HTMLInputElement
    const signal = screen.getByLabelText('Signal Period') as HTMLInputElement
    expect(fast.value).toBe('12')
    expect(slow.value).toBe('26')
    expect(signal.value).toBe('9')
  })

  it('edit mode: when initialParams is passed, inputs show those values not defaults', () => {
    render(
      <IndicatorParamForm
        type={smaType}
        initialParams={{ period: 50 }}
        submitLabel="Save"
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    )
    const input = screen.getByLabelText('Period') as HTMLInputElement
    expect(input.value).toBe('50')
  })

  it('submit button is disabled when a field value is out of range', () => {
    render(
      <IndicatorParamForm
        type={smaType}
        initialParams={{ period: 1 }}  // min is 2
        submitLabel="Add"
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    )
    const submitBtn = screen.getByText('Add') as HTMLButtonElement
    expect(submitBtn.disabled).toBe(true)
  })

  it('submit button is enabled when field is valid; clicking it calls onSubmit with coerced params', () => {
    const onSubmit = vi.fn()
    render(
      <IndicatorParamForm
        type={smaType}
        submitLabel="Add"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />
    )
    const input = screen.getByLabelText('Period') as HTMLInputElement
    fireEvent.change(input, { target: { value: '30' } })

    const submitBtn = screen.getByText('Add') as HTMLButtonElement
    expect(submitBtn.disabled).toBe(false)
    fireEvent.click(submitBtn)

    expect(onSubmit).toHaveBeenCalledOnce()
    expect(onSubmit).toHaveBeenCalledWith({ period: 30 })
  })

  it('clicking Cancel calls onCancel', () => {
    const onCancel = vi.fn()
    render(
      <IndicatorParamForm
        type={smaType}
        submitLabel="Add"
        onSubmit={vi.fn()}
        onCancel={onCancel}
      />
    )
    fireEvent.click(screen.getByText('Cancel'))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('int field: typing "3.7" is coerced to integer 3 on submit', () => {
    const onSubmit = vi.fn()
    render(
      <IndicatorParamForm
        type={smaType}
        submitLabel="Add"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />
    )
    // parseInt("3.7") => 3, which is >= min 2
    const input = screen.getByLabelText('Period') as HTMLInputElement
    fireEvent.change(input, { target: { value: '3.7' } })

    const submitBtn = screen.getByText('Add') as HTMLButtonElement
    // 3 is valid (>= 2, <= 500), so should be enabled
    expect(submitBtn.disabled).toBe(false)
    // Submit the form directly to bypass jsdom click→submit limitations
    const form = submitBtn.closest('form')!
    fireEvent.submit(form)
    expect(onSubmit).toHaveBeenCalledWith({ period: 3 })
  })

  it('shows inline error message when field is out of range', () => {
    render(
      <IndicatorParamForm
        type={smaType}
        initialParams={{ period: 600 }}  // max is 500
        submitLabel="Add"
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    )
    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.getByRole('alert').textContent).toContain('at most 500')
  })

  it('does not call onSubmit when validation fails', () => {
    const onSubmit = vi.fn()
    render(
      <IndicatorParamForm
        type={smaType}
        initialParams={{ period: 1 }}  // below min
        submitLabel="Add"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />
    )
    // Submit button is disabled, but test via programmatic form submission
    const form = screen.getByText('Add').closest('form')
    if (form) fireEvent.submit(form)
    expect(onSubmit).not.toHaveBeenCalled()
  })

  const spikeEnumType = {
    type: 'Spike',
    labelTemplate: 'Spike',
    display: 'overlay' as const,
    outputs: [] as readonly string[],
    params: [
      {
        name: 'move_method',
        type: 'enum' as const,
        default: 'EXCURSION',
        choices: ['NET', 'EXCURSION', 'RANGE'] as readonly string[],
        label: 'Move method',
      },
    ],
  }

  it('renders a Select for enum params with the default selected', () => {
    render(
      <IndicatorParamForm
        type={spikeEnumType as any}
        submitLabel="Save"
        onSubmit={() => {}}
        onCancel={() => {}}
      />,
    )
    // shadcn Select uses combobox role for its trigger
    const combobox = screen.getByRole('combobox', { name: 'Move method' })
    expect(combobox).toBeTruthy()
    expect(combobox.textContent).toContain('EXCURSION')
  })
})
