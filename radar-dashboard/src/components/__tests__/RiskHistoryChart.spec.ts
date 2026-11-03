import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import RiskHistoryChart from '../RiskHistoryChart.vue'
import type { ScoreHistoryPoint, SeverityRiskPoint } from '@/api/client'

// Same narrow exception as ScoreHistoryChart.spec.ts: jsdom has no canvas 2D context.
vi.mock('vue-chartjs', () => ({
  Line: {
    name: 'LineStub',
    props: ['data', 'options'],
    template: '<div />',
  },
}))

const WEIGHTS = { CRITICAL: 64, HIGH: 16, MEDIUM: 4, LOW: 1 } as const

function risk(counts: Partial<Record<keyof typeof WEIGHTS, number>>, excluded = 0): SeverityRiskPoint[] {
  return (Object.keys(WEIGHTS) as (keyof typeof WEIGHTS)[]).map((severity) => ({
    severity,
    weight: WEIGHTS[severity],
    count: counts[severity] ?? 0,
    excluded: severity === 'LOW' ? excluded : 0,
    wont_fix: 0,
    weighted: (counts[severity] ?? 0) * WEIGHTS[severity],
  }))
}

function makePoint(id: number, scoredAt: string, entries: SeverityRiskPoint[]): ScoreHistoryPoint {
  return {
    scoring_run_id: id,
    audit_id: id,
    commit_sha: 'a'.repeat(40),
    scored_at: scoredAt,
    global_score: 5,
    categories: [],
    risk: entries,
    risk_index: entries.reduce((sum, entry) => sum + entry.weighted, 0),
  }
}

const twoPoints = [
  makePoint(1, '2026-01-01T10:00:00Z', risk({ CRITICAL: 2, HIGH: 61, MEDIUM: 55, LOW: 512 }, 2)),
  makePoint(2, '2026-02-01T10:00:00Z', risk({ HIGH: 40, MEDIUM: 50, LOW: 400 })),
]

describe('RiskHistoryChart', () => {
  it('shows a short-history message with fewer than two audits', () => {
    const wrapper = mount(RiskHistoryChart, { props: { points: [twoPoints[0]!] } })

    expect(wrapper.text()).toContain('Only one audit so far')
    expect(wrapper.findComponent({ name: 'LineStub' }).exists()).toBe(false)
  })

  it('stacks one filled layer per severity, critical at the bottom', () => {
    const wrapper = mount(RiskHistoryChart, { props: { points: twoPoints } })

    const data = wrapper.findComponent({ name: 'LineStub' }).props('data')
    expect(data.datasets.map((d: { label: string }) => d.label)).toEqual([
      'Critical',
      'High',
      'Medium',
      'Low',
    ])
    expect(data.datasets[0].fill).toBe('origin')
    expect(data.datasets[1].fill).toBe('-1')
    expect(data.datasets[1].data).toEqual([
      { x: new Date('2026-01-01T10:00:00Z').getTime(), y: 976 },
      { x: new Date('2026-02-01T10:00:00Z').getTime(), y: 640 },
    ])
    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    expect(options.scales.y.stacked).toBe(true)
  })

  it('explains raw count, weight and excluded findings in the tooltip', () => {
    const wrapper = mount(RiskHistoryChart, { props: { points: twoPoints } })

    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    const label = options.plugins.tooltip.callbacks.label({ datasetIndex: 3, dataIndex: 0 })
    expect(label).toBe('Low: 512 open x 1 = 512 (+2 excluded)')
    const footer = options.plugins.tooltip.callbacks.footer([{ dataIndex: 0 }])
    expect(footer).toBe('Risk index: 1836')
    const noExcluded = options.plugins.tooltip.callbacks.label({ datasetIndex: 0, dataIndex: 1 })
    expect(noExcluded).toBe('Critical: 0 open x 64 = 0')
  })

  it('reads the weights shown in the caption from the API data', () => {
    const wrapper = mount(RiskHistoryChart, { props: { points: twoPoints } })

    expect(wrapper.text()).toContain('critical x64, high x16, medium x4, low x1')
  })

  it('treats a severity missing from a point as zero', () => {
    const sparse = [twoPoints[0]!, { ...twoPoints[1]!, risk: [] }]
    const wrapper = mount(RiskHistoryChart, { props: { points: sparse } })

    const data = wrapper.findComponent({ name: 'LineStub' }).props('data')
    expect(data.datasets[0].data[1].y).toBe(0)
  })

  it('emits select-point when an audit is clicked on the chart', () => {
    const wrapper = mount(RiskHistoryChart, { props: { points: twoPoints } })

    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    options.onClick({}, [{ index: 0 }])
    expect(wrapper.emitted('select-point')).toEqual([[1]])
  })

  it('lists every audit with its risk index for keyboard users and emits select-point', async () => {
    const wrapper = mount(RiskHistoryChart, { props: { points: twoPoints } })

    const buttons = wrapper.findAll('.risk-history-chart__list button')
    expect(buttons[0]!.text()).toContain('risk index 1836 (2 critical, 61 high, 55 medium, 512 low)')
    await buttons[1]!.trigger('click')
    expect(wrapper.emitted('select-point')).toEqual([[2]])
  })
})
