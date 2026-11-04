import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ReportSeveritySummary from '../ReportSeveritySummary.vue'
import type { CategoryReport, CriterionReport, FindingReport } from '@/api/client'

function makeFinding(
  id: number,
  severity: FindingReport['severity'],
  humanVerdict = 'UNREVIEWED',
): FindingReport {
  return {
    id,
    severity,
    description: `finding ${id}`,
    file: null,
    line: null,
    status: 'OPEN',
    human_verdict: humanVerdict,
    recommendation: null,
  }
}

function makeCriterion(id: number, name: string, findings: FindingReport[]): CriterionReport {
  return { id, name, status: 'scored', value: 5, na_reason: null, findings }
}

function makeCategory(
  id: number,
  name: string,
  order: number,
  criteria: CriterionReport[],
): CategoryReport {
  return { id, name, order, status: 'scored', value: 5, confidence: 'HIGH', criteria }
}

describe('ReportSeveritySummary', () => {
  it('renders one chip per severity present, in descending priority order', () => {
    const categories = [
      makeCategory(1, 'Code quality', 1, [
        makeCriterion(10, 'Linting', [makeFinding(1, 'HIGH')]),
        makeCriterion(11, 'Complexity', [makeFinding(2, 'CRITICAL')]),
      ]),
    ]

    const wrapper = mount(ReportSeveritySummary, { props: { categories } })

    const chips = wrapper.findAll('[data-testid="severity-chip"]')
    expect(chips.map((c) => c.text())).toEqual(['CRITICAL (1 / 1)', 'HIGH (1 / 1)'])
  })

  it('does not render a chip for a severity with zero findings', () => {
    const categories = [
      makeCategory(1, 'Code quality', 1, [makeCriterion(10, 'Linting', [makeFinding(1, 'INFO')])]),
    ]

    const wrapper = mount(ReportSeveritySummary, { props: { categories } })

    expect(wrapper.text()).not.toContain('CRITICAL')
    expect(wrapper.text()).toContain('INFO (1 / 1)')
  })

  it('counts distinct criteria and total findings separately', () => {
    const categories = [
      makeCategory(1, 'Code quality', 1, [
        makeCriterion(10, 'Linting', [makeFinding(1, 'HIGH'), makeFinding(2, 'HIGH')]),
        makeCriterion(11, 'Complexity', [makeFinding(3, 'HIGH')]),
      ]),
    ]

    const wrapper = mount(ReportSeveritySummary, { props: { categories } })

    expect(wrapper.find('[data-testid="severity-chip"]').text()).toBe('HIGH (2 / 3)')
  })

  it('shows no criterion list until the chip is clicked, then lists affected criteria as anchor links', async () => {
    const categories = [
      makeCategory(1, 'Code quality', 1, [
        makeCriterion(10, 'Linting', [makeFinding(1, 'CRITICAL')]),
      ]),
    ]

    const wrapper = mount(ReportSeveritySummary, { props: { categories } })
    expect(wrapper.find('[data-testid="severity-criterion-link"]').exists()).toBe(false)

    await wrapper.find('[data-testid="severity-chip"]').trigger('click')

    const link = wrapper.find('[data-testid="severity-criterion-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('#criterion-10')
    expect(link.text()).toBe('Code quality / Linting')
  })

  it('lists each affected criterion once per severity, in report order', async () => {
    const categories = [
      makeCategory(2, 'Security', 2, [
        makeCriterion(20, 'Secrets', [makeFinding(1, 'CRITICAL'), makeFinding(2, 'CRITICAL')]),
      ]),
      makeCategory(1, 'Code quality', 1, [
        makeCriterion(10, 'Linting', [makeFinding(3, 'CRITICAL')]),
      ]),
    ]

    const wrapper = mount(ReportSeveritySummary, { props: { categories } })
    await wrapper.find('[data-testid="severity-chip"]').trigger('click')

    const links = wrapper.findAll('[data-testid="severity-criterion-link"]')
    expect(links.map((l) => l.text())).toEqual(['Security / Secrets', 'Code quality / Linting'])
  })

  it('toggles the criterion list closed on a second click', async () => {
    const categories = [
      makeCategory(1, 'Code quality', 1, [
        makeCriterion(10, 'Linting', [makeFinding(1, 'CRITICAL')]),
      ]),
    ]

    const wrapper = mount(ReportSeveritySummary, { props: { categories } })
    const chip = wrapper.find('[data-testid="severity-chip"]')

    await chip.trigger('click')
    expect(wrapper.find('[data-testid="severity-criterion-link"]').exists()).toBe(true)

    await chip.trigger('click')
    expect(wrapper.find('[data-testid="severity-criterion-link"]').exists()).toBe(false)
  })

  it('renders nothing when there are no findings at all', () => {
    const categories = [makeCategory(1, 'Code quality', 1, [makeCriterion(10, 'Linting', [])])]

    const wrapper = mount(ReportSeveritySummary, { props: { categories } })

    expect(wrapper.findAll('[data-testid="severity-chip"]')).toHaveLength(0)
  })

  it('leaves false positives out of the counts and notes how many were dismissed', () => {
    const categories = [
      makeCategory(1, 'Code quality', 1, [
        makeCriterion(10, 'Linting', [
          makeFinding(1, 'HIGH'),
          makeFinding(2, 'HIGH', 'FALSE_POSITIVE'),
        ]),
        makeCriterion(11, 'Complexity', [makeFinding(3, 'CRITICAL', 'FALSE_POSITIVE')]),
      ]),
    ]

    const wrapper = mount(ReportSeveritySummary, { props: { categories } })

    const chips = wrapper.findAll('[data-testid="severity-chip"]')
    expect(chips.map((c) => c.text())).toEqual(['HIGH (1 / 1)'])
    expect(wrapper.find('[data-testid="dismissed-count"]').text()).toBe(
      '2 findings dismissed as false positive, not counted',
    )
  })

  it('still shows the dismissed note when every finding is a false positive', () => {
    const categories = [
      makeCategory(1, 'Code quality', 1, [
        makeCriterion(10, 'Linting', [makeFinding(1, 'HIGH', 'FALSE_POSITIVE')]),
      ]),
    ]

    const wrapper = mount(ReportSeveritySummary, { props: { categories } })

    expect(wrapper.findAll('[data-testid="severity-chip"]')).toHaveLength(0)
    expect(wrapper.find('[data-testid="dismissed-count"]').text()).toBe(
      '1 finding dismissed as false positive, not counted',
    )
  })

  it('shows no dismissed note when nothing is a false positive', () => {
    const categories = [
      makeCategory(1, 'Code quality', 1, [makeCriterion(10, 'Linting', [makeFinding(1, 'HIGH')])]),
    ]

    const wrapper = mount(ReportSeveritySummary, { props: { categories } })

    expect(wrapper.find('[data-testid="dismissed-count"]').exists()).toBe(false)
  })
})
