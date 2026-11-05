import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CriterionFindings from '../CriterionFindings.vue'
import { getCriterionFindings } from '@/api/client'
import type { CriterionReport, FindingReport } from '@/api/client'

vi.mock('@/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/client')>()),
  getCriterionFindings: vi.fn<typeof getCriterionFindings>(),
}))

function makeFinding(
  id: number,
  severity: FindingReport['severity'],
  file: string | null = null,
  humanVerdict = 'UNREVIEWED',
): FindingReport {
  return {
    id,
    severity,
    description: `finding ${id}`,
    file,
    line: null,
    status: 'OPEN',
    human_verdict: humanVerdict,
    verdict_note: null,
    recommendation: null,
  }
}

/** The criterion as the report sends it: `findings` is the first page, counts cover all. */
function makeCriterion(
  findings: FindingReport[],
  overrides: Partial<CriterionReport> = {},
): CriterionReport {
  const severityCounts: Record<string, number> = {}
  for (const finding of findings.filter((f) => f.human_verdict !== 'FALSE_POSITIVE')) {
    severityCounts[finding.severity] = (severityCounts[finding.severity] ?? 0) + 1
  }
  return {
    id: 12,
    name: 'Type checking',
    status: 'scored',
    implemented: true,
    value: 5,
    na_reason: null,
    findings,
    findings_total: findings.length,
    severity_counts: severityCounts,
    dismissed_count: findings.length - Object.values(severityCounts).reduce((a, b) => a + b, 0),
    ...overrides,
  }
}

function propsFor(findings: FindingReport[], overrides: Partial<CriterionReport> = {}) {
  return { criterion: makeCriterion(findings, overrides), repositoryId: 1, scoringRunId: 34 }
}

describe('CriterionFindings', () => {
  beforeEach(() => {
    vi.mocked(getCriterionFindings).mockReset()
  })

  it('renders one chip per severity present, in descending priority order, with counts', () => {
    const findings = [
      makeFinding(1, 'HIGH'),
      makeFinding(2, 'CRITICAL'),
      makeFinding(3, 'HIGH'),
      makeFinding(4, 'LOW'),
    ]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })

    const chips = wrapper.findAll('[data-testid="severity-chip"]')
    expect(chips.map((c) => c.text())).toEqual(['CRITICAL (1)', 'HIGH (2)', 'LOW (1)'])
  })

  it('does not render a chip for a severity with zero findings', () => {
    const findings = [makeFinding(1, 'INFO')]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })

    expect(wrapper.text()).not.toContain('CRITICAL')
    expect(wrapper.text()).not.toContain('HIGH')
    expect(wrapper.text()).not.toContain('MEDIUM')
    expect(wrapper.text()).not.toContain('LOW (')
    expect(wrapper.text()).toContain('INFO (1)')
  })

  it('shows no findings until a chip is clicked, then shows only that severity', async () => {
    const findings = [makeFinding(1, 'CRITICAL'), makeFinding(2, 'HIGH')]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })
    expect(wrapper.findAllComponents({ name: 'FindingCard' })).toHaveLength(0)

    const chips = wrapper.findAll('[data-testid="severity-chip"]')
    await chips[0]!.trigger('click')

    const cards = wrapper.findAllComponents({ name: 'FindingCard' })
    expect(cards).toHaveLength(1)
    expect(cards[0]!.props('finding').severity).toBe('CRITICAL')
  })

  it('reflects the expanded state on the chip via aria-expanded and an arrow indicator', async () => {
    const findings = [makeFinding(1, 'CRITICAL')]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })
    const chip = wrapper.find('[data-testid="severity-chip"]')

    expect(chip.attributes('aria-expanded')).toBe('false')
    expect(chip.find('[data-testid="chip-arrow"]').exists()).toBe(true)

    await chip.trigger('click')

    expect(chip.attributes('aria-expanded')).toBe('true')
  })

  it('toggles a severity group closed on a second click', async () => {
    const findings = [makeFinding(1, 'CRITICAL')]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })
    const chip = wrapper.find('[data-testid="severity-chip"]')

    await chip.trigger('click')
    expect(wrapper.findAllComponents({ name: 'FindingCard' })).toHaveLength(1)

    await chip.trigger('click')
    expect(wrapper.findAllComponents({ name: 'FindingCard' })).toHaveLength(0)
  })

  it('forwards a FindingCard updated event as its own updated event', async () => {
    const findings = [makeFinding(1, 'CRITICAL')]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })
    await wrapper.find('[data-testid="severity-chip"]').trigger('click')

    await wrapper.findComponent({ name: 'FindingCard' }).vm.$emit('updated')

    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('groups same-severity findings sharing a file under one heading', async () => {
    const findings = [
      makeFinding(1, 'HIGH', 'src/a.py'),
      makeFinding(2, 'HIGH', 'src/a.py'),
      makeFinding(3, 'HIGH', 'src/b.py'),
    ]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })
    await wrapper.find('[data-testid="severity-chip"]').trigger('click')

    const headings = wrapper.findAll('.criterion-findings__file-heading')
    expect(headings.map((h) => h.text())).toEqual(['src/a.py', 'src/b.py'])

    const cards = wrapper.findAllComponents({ name: 'FindingCard' })
    expect(cards).toHaveLength(3)
    expect(cards.every((c) => c.props('showFile') === false)).toBe(true)
  })

  it('merges a non-contiguous file reappearance into its earlier cluster', async () => {
    const findings = [
      makeFinding(1, 'HIGH', 'src/a.py'),
      makeFinding(2, 'HIGH', 'src/b.py'),
      makeFinding(3, 'HIGH', 'src/a.py'),
    ]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })
    await wrapper.find('[data-testid="severity-chip"]').trigger('click')

    const headings = wrapper.findAll('.criterion-findings__file-heading')
    expect(headings.map((h) => h.text())).toEqual(['src/a.py', 'src/b.py'])

    const cards = wrapper.findAllComponents({ name: 'FindingCard' })
    expect(cards.map((c) => c.props('finding').id)).toEqual([1, 3, 2])
  })

  it('renders no file heading and leaves showFile true for a fileless finding', async () => {
    const findings = [makeFinding(1, 'HIGH', null)]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })
    await wrapper.find('[data-testid="severity-chip"]').trigger('click')

    expect(wrapper.find('.criterion-findings__file-heading').exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'FindingCard' }).props('showFile')).toBe(true)
  })

  it('does not mix file groups across different severities', async () => {
    const findings = [makeFinding(1, 'CRITICAL', 'src/a.py'), makeFinding(2, 'LOW', 'src/a.py')]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })
    const chips = wrapper.findAll('[data-testid="severity-chip"]')
    await chips[0]!.trigger('click')
    await chips[1]!.trigger('click')

    const headings = wrapper.findAll('.criterion-findings__file-heading')
    expect(headings).toHaveLength(2)
    expect(headings.every((h) => h.text() === 'src/a.py')).toBe(true)
  })

  it('leaves false positives out of the severity chip counts', () => {
    const findings = [
      makeFinding(1, 'HIGH'),
      makeFinding(2, 'HIGH', null, 'FALSE_POSITIVE'),
      makeFinding(3, 'LOW', null, 'FALSE_POSITIVE'),
    ]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })

    const chips = wrapper.findAll('[data-testid="severity-chip"]')
    expect(chips.map((c) => c.text())).toEqual(['HIGH (1)'])
  })

  it('lists false positives in a collapsed dismissed section where the verdict can be reverted', async () => {
    const findings = [makeFinding(1, 'HIGH'), makeFinding(2, 'LOW', null, 'FALSE_POSITIVE')]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })

    const dismissed = wrapper.find('[data-testid="dismissed-findings"]')
    expect(dismissed.element.tagName).toBe('DETAILS')
    expect(dismissed.attributes('open')).toBeUndefined()
    expect(dismissed.find('summary').text()).toBe('Dismissed as false positive (1)')
    const cards = wrapper
      .findAllComponents({ name: 'FindingCard' })
      .filter((card) => dismissed.element.contains(card.element))
    expect(cards.map((c) => c.props('finding').id)).toEqual([2])

    await cards[0]!.vm.$emit('updated')
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('renders no dismissed section when nothing is a false positive', () => {
    const wrapper = mount(CriterionFindings, { props: propsFor([makeFinding(1, 'HIGH')]) })

    expect(wrapper.find('[data-testid="dismissed-findings"]').exists()).toBe(false)
  })

  it("keeps resolved and won't-fix findings in the counts unless they are false positives", () => {
    const findings = [
      { ...makeFinding(1, 'HIGH'), status: 'WONT_FIX' },
      { ...makeFinding(2, 'HIGH'), status: 'RESOLVED', human_verdict: 'TRUE_POSITIVE' },
      { ...makeFinding(3, 'HIGH', null, 'FALSE_POSITIVE'), status: 'WONT_FIX' },
    ]

    const wrapper = mount(CriterionFindings, { props: propsFor(findings) })

    expect(wrapper.find('[data-testid="severity-chip"]').text()).toBe('HIGH (2)')
  })

  describe('pagination', () => {
    // First page holds findings 1-2, the criterion has 5 (4 HIGH, 1 dismissed).
    const firstPage = [makeFinding(1, 'HIGH'), makeFinding(2, 'HIGH')]
    const paged = { findings_total: 5, severity_counts: { HIGH: 4 }, dismissed_count: 1 }

    it('counts chips and dismissed findings from the server totals, not the loaded page', () => {
      const wrapper = mount(CriterionFindings, { props: propsFor(firstPage, paged) })

      expect(wrapper.find('[data-testid="severity-chip"]').text()).toBe('HIGH (4)')
      expect(wrapper.find('[data-testid="dismissed-findings"] summary').text()).toBe(
        'Dismissed as false positive (1)',
      )
    })

    it('shows no more link while every group is collapsed', () => {
      const wrapper = mount(CriterionFindings, { props: propsFor(firstPage, paged) })

      expect(wrapper.find('[data-testid="more-findings"]').exists()).toBe(false)
    })

    it('shows no more link once every finding is loaded', async () => {
      const wrapper = mount(CriterionFindings, { props: propsFor(firstPage) })
      await wrapper.find('[data-testid="severity-chip"]').trigger('click')

      expect(wrapper.find('[data-testid="more-findings"]').exists()).toBe(false)
    })

    it('loads the next page from the current offset and hides the link at the end', async () => {
      vi.mocked(getCriterionFindings).mockResolvedValueOnce([
        makeFinding(3, 'HIGH'),
        makeFinding(4, 'HIGH'),
        makeFinding(5, 'LOW', null, 'FALSE_POSITIVE'),
      ])
      const wrapper = mount(CriterionFindings, { props: propsFor(firstPage, paged) })
      await wrapper.find('[data-testid="severity-chip"]').trigger('click')
      const more = wrapper.find('[data-testid="more-findings"]')
      expect(more.text()).toBe('More (3 remaining)')

      await more.trigger('click')
      await flushPromises()

      expect(getCriterionFindings).toHaveBeenCalledWith(1, 12, 34, 2)
      const cards = wrapper.findAllComponents({ name: 'FindingCard' })
      expect(cards.map((c) => c.props('finding').id)).toEqual([1, 2, 3, 4, 5])
      expect(wrapper.find('[data-testid="more-findings"]').exists()).toBe(false)
    })

    it('reloads the pages already shown when the report is refetched', async () => {
      vi.mocked(getCriterionFindings)
        .mockResolvedValueOnce([makeFinding(3, 'HIGH')])
        .mockResolvedValueOnce([{ ...makeFinding(3, 'HIGH'), human_verdict: 'TRUE_POSITIVE' }])
      const wrapper = mount(CriterionFindings, { props: propsFor(firstPage, paged) })
      await wrapper.find('[data-testid="severity-chip"]').trigger('click')
      await wrapper.find('[data-testid="more-findings"]').trigger('click')
      await flushPromises()

      await wrapper.setProps({ criterion: makeCriterion(firstPage, paged) })
      await flushPromises()

      expect(getCriterionFindings).toHaveBeenLastCalledWith(1, 12, 34, 2)
      const reloaded = wrapper
        .findAllComponents({ name: 'FindingCard' })
        .map((c) => c.props('finding'))
        .find((f) => f.id === 3)
      expect(reloaded?.human_verdict).toBe('TRUE_POSITIVE')
    })

    it('drops the extra pages without fetching when another scoring run is shown', async () => {
      vi.mocked(getCriterionFindings).mockResolvedValueOnce([makeFinding(3, 'HIGH')])
      const wrapper = mount(CriterionFindings, { props: propsFor(firstPage, paged) })
      await wrapper.find('[data-testid="severity-chip"]').trigger('click')
      await wrapper.find('[data-testid="more-findings"]').trigger('click')
      await flushPromises()

      await wrapper.setProps({ criterion: makeCriterion(firstPage, paged), scoringRunId: 35 })
      await flushPromises()

      expect(getCriterionFindings).toHaveBeenCalledTimes(1)
      expect(wrapper.findAllComponents({ name: 'FindingCard' })).toHaveLength(2)
    })

    it('drops the extra pages when reloading them fails, rather than keep stale verdicts', async () => {
      vi.mocked(getCriterionFindings)
        .mockResolvedValueOnce([makeFinding(3, 'HIGH')])
        .mockRejectedValueOnce(new Error('network down'))
      const wrapper = mount(CriterionFindings, { props: propsFor(firstPage, paged) })
      await wrapper.find('[data-testid="severity-chip"]').trigger('click')
      await wrapper.find('[data-testid="more-findings"]').trigger('click')
      await flushPromises()

      await wrapper.setProps({ criterion: makeCriterion(firstPage, paged) })
      await flushPromises()

      expect(wrapper.findAllComponents({ name: 'FindingCard' })).toHaveLength(2)
      expect(wrapper.find('[role="alert"]').text()).toContain('network down')
      expect(wrapper.find('[data-testid="more-findings"]').text()).toBe('More (3 remaining)')
    })

    it('shows an error and keeps the link when a page fails to load', async () => {
      vi.mocked(getCriterionFindings).mockRejectedValueOnce(new Error('network down'))
      const wrapper = mount(CriterionFindings, { props: propsFor(firstPage, paged) })
      await wrapper.find('[data-testid="severity-chip"]').trigger('click')

      await wrapper.find('[data-testid="more-findings"]').trigger('click')
      await flushPromises()

      expect(wrapper.find('[role="alert"]').text()).toContain('network down')
      expect(wrapper.find('[data-testid="more-findings"]').exists()).toBe(true)
    })
  })
})
