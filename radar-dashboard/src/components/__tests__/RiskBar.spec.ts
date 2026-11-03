import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RiskBar from '../RiskBar.vue'
import type { SeverityRiskPoint } from '@/api/client'

const WEIGHTS = { CRITICAL: 64, HIGH: 16, MEDIUM: 4, LOW: 1 } as const

function risk(counts: Partial<Record<keyof typeof WEIGHTS, number>>): SeverityRiskPoint[] {
  return (Object.keys(WEIGHTS) as (keyof typeof WEIGHTS)[]).map((severity) => ({
    severity,
    weight: WEIGHTS[severity],
    count: counts[severity] ?? 0,
    excluded: 0,
    weighted: (counts[severity] ?? 0) * WEIGHTS[severity],
  }))
}

function mountBar(counts: Partial<Record<keyof typeof WEIGHTS, number>>) {
  const entries = risk(counts)
  const riskIndex = entries.reduce((sum, entry) => sum + entry.weighted, 0)
  return mount(RiskBar, { props: { risk: entries, riskIndex } })
}

describe('RiskBar', () => {
  it('shows the total weighted risk', () => {
    const wrapper = mountBar({ CRITICAL: 1, HIGH: 2, LOW: 4 })

    expect(wrapper.find('[data-testid="risk-total"]').text()).toBe('100')
  })

  it('draws one segment per severity with risk, sized by its share of the total', () => {
    const wrapper = mountBar({ CRITICAL: 1, HIGH: 2, LOW: 4 })

    const segments = wrapper.findAll('[data-testid="risk-segment"]')
    expect(segments.map((s) => s.classes())).toEqual([
      expect.arrayContaining(['risk-bar__segment--critical']),
      expect.arrayContaining(['risk-bar__segment--high']),
      expect.arrayContaining(['risk-bar__segment--low']),
    ])
    expect(segments.map((s) => s.attributes('style'))).toEqual([
      'flex-grow: 64;',
      'flex-grow: 32;',
      'flex-grow: 4;',
    ])
  })

  it('labels each severity with its count, weight and weighted value, skipping empty ones', () => {
    const wrapper = mountBar({ CRITICAL: 1, HIGH: 2, LOW: 4 })

    const labels = wrapper.findAll('[data-testid="risk-legend-item"]').map((item) => item.text())
    expect(labels).toEqual(['Critical 1 x64 = 64', 'High 2 x16 = 32', 'Low 4 x1 = 4'])
  })

  it('fills the bar with the neutral blue and says so when there is no open risk', () => {
    const wrapper = mountBar({})

    expect(wrapper.find('[data-testid="risk-total"]').text()).toBe('0')
    expect(wrapper.findAll('[data-testid="risk-segment"]')).toHaveLength(0)
    expect(wrapper.find('.risk-bar__track').classes()).toContain('risk-bar__track--clear')
    expect(wrapper.text()).toContain('No open finding')
  })

  it('hides the drawn bar from assistive technology, the legend carries the numbers', () => {
    const wrapper = mountBar({ HIGH: 1 })

    expect(wrapper.find('.risk-bar__track').attributes('aria-hidden')).toBe('true')
  })
})
