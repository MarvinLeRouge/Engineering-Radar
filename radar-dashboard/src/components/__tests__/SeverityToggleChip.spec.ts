import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SeverityToggleChip from '../SeverityToggleChip.vue'

describe('SeverityToggleChip', () => {
  it('renders the severity and count label', () => {
    const wrapper = mount(SeverityToggleChip, {
      props: { severity: 'CRITICAL', countLabel: '3 / 57', expanded: false },
    })

    expect(wrapper.text()).toContain('CRITICAL (3 / 57)')
  })

  it('applies a severity-specific color class', () => {
    const wrapper = mount(SeverityToggleChip, {
      props: { severity: 'HIGH', countLabel: '2', expanded: false },
    })

    expect(wrapper.find('[data-testid="severity-chip"]').classes()).toContain(
      'severity-toggle-chip--high',
    )
  })

  it('reflects expanded state via aria-expanded and an arrow indicator', () => {
    const wrapper = mount(SeverityToggleChip, {
      props: { severity: 'LOW', countLabel: '1', expanded: true },
    })

    const chip = wrapper.find('[data-testid="severity-chip"]')
    expect(chip.attributes('aria-expanded')).toBe('true')
    expect(chip.find('[data-testid="chip-arrow"]').classes()).toContain(
      'severity-toggle-chip__arrow--open',
    )
  })

  it('emits toggle on click', async () => {
    const wrapper = mount(SeverityToggleChip, {
      props: { severity: 'INFO', countLabel: '1', expanded: false },
    })

    await wrapper.find('[data-testid="severity-chip"]').trigger('click')

    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })
})
