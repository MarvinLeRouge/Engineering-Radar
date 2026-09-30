import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CriterionFindings from '../CriterionFindings.vue'
import type { FindingReport } from '@/api/client'

function makeFinding(id: number, severity: FindingReport['severity']): FindingReport {
  return {
    id,
    severity,
    description: `finding ${id}`,
    file: null,
    line: null,
    status: 'OPEN',
    human_verdict: 'UNREVIEWED',
    recommendation: null,
  }
}

describe('CriterionFindings', () => {
  it('renders one chip per severity present, in descending priority order, with counts', () => {
    const findings = [
      makeFinding(1, 'HIGH'),
      makeFinding(2, 'CRITICAL'),
      makeFinding(3, 'HIGH'),
      makeFinding(4, 'LOW'),
    ]

    const wrapper = mount(CriterionFindings, { props: { findings } })

    const chips = wrapper.findAll('[data-testid="severity-chip"]')
    expect(chips.map((c) => c.text())).toEqual(['CRITICAL (1)', 'HIGH (2)', 'LOW (1)'])
  })

  it('does not render a chip for a severity with zero findings', () => {
    const findings = [makeFinding(1, 'INFO')]

    const wrapper = mount(CriterionFindings, { props: { findings } })

    expect(wrapper.text()).not.toContain('CRITICAL')
    expect(wrapper.text()).not.toContain('HIGH')
    expect(wrapper.text()).not.toContain('MEDIUM')
    expect(wrapper.text()).not.toContain('LOW (')
    expect(wrapper.text()).toContain('INFO (1)')
  })

  it('shows no findings until a chip is clicked, then shows only that severity', async () => {
    const findings = [makeFinding(1, 'CRITICAL'), makeFinding(2, 'HIGH')]

    const wrapper = mount(CriterionFindings, { props: { findings } })
    expect(wrapper.findAllComponents({ name: 'FindingCard' })).toHaveLength(0)

    const chips = wrapper.findAll('[data-testid="severity-chip"]')
    await chips[0]!.trigger('click')

    const cards = wrapper.findAllComponents({ name: 'FindingCard' })
    expect(cards).toHaveLength(1)
    expect(cards[0]!.props('finding').severity).toBe('CRITICAL')
  })

  it('toggles a severity group closed on a second click', async () => {
    const findings = [makeFinding(1, 'CRITICAL')]

    const wrapper = mount(CriterionFindings, { props: { findings } })
    const chip = wrapper.find('[data-testid="severity-chip"]')

    await chip.trigger('click')
    expect(wrapper.findAllComponents({ name: 'FindingCard' })).toHaveLength(1)

    await chip.trigger('click')
    expect(wrapper.findAllComponents({ name: 'FindingCard' })).toHaveLength(0)
  })

  it('forwards a FindingCard updated event as its own updated event', async () => {
    const findings = [makeFinding(1, 'CRITICAL')]

    const wrapper = mount(CriterionFindings, { props: { findings } })
    await wrapper.find('[data-testid="severity-chip"]').trigger('click')

    await wrapper.findComponent({ name: 'FindingCard' }).vm.$emit('updated')

    expect(wrapper.emitted('updated')).toHaveLength(1)
  })
})
