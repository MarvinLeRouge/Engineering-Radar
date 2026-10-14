import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ScoreHistoryChart from '../ScoreHistoryChart.vue'
import type { ScoreHistoryPoint } from '@/api/client'

// Mocked solely because jsdom has no real <canvas> 2D context (Chart.js
// would throw on getContext); this is a narrow exception for the charting
// library's own rendering internals, not a general mocking precedent -- the
// rest of this codebase deliberately invokes real code/tools in tests.
vi.mock('vue-chartjs', () => ({
  Line: {
    name: 'LineStub',
    props: ['data', 'options'],
    template: '<div />',
  },
}))

function makePoint(id: number, scoredAt: string, globalScore: number | null): ScoreHistoryPoint {
  return { scoring_run_id: id, audit_id: id, commit_sha: 'a'.repeat(40), scored_at: scoredAt, global_score: globalScore }
}

describe('ScoreHistoryChart', () => {
  it('shows an empty-state message when there is no history', () => {
    const wrapper = mount(ScoreHistoryChart, { props: { points: [] } })

    expect(wrapper.text()).toContain('No audit history yet.')
    expect(wrapper.findComponent({ name: 'LineStub' }).exists()).toBe(false)
  })

  it('shows a short-history message when there is only one audit', () => {
    const wrapper = mount(ScoreHistoryChart, {
      props: { points: [makePoint(1, '2026-01-01', 7)] },
    })

    expect(wrapper.text()).toContain('Only one audit so far')
    expect(wrapper.findComponent({ name: 'LineStub' }).exists()).toBe(false)
  })

  it('renders the chart with one data point per audit, in order', () => {
    const points = [makePoint(1, '2026-01-01', 5), makePoint(2, '2026-02-01', 7)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    const chart = wrapper.findComponent({ name: 'LineStub' })
    expect(chart.exists()).toBe(true)
    const data = chart.props('data')
    expect(data.datasets[0].data).toEqual([
      { x: new Date('2026-01-01').getTime(), y: 5 },
      { x: new Date('2026-02-01').getTime(), y: 7 },
    ])
  })

  it('fixes the y-axis to the 0-10 range', () => {
    const points = [makePoint(1, '2026-01-01', 5), makePoint(2, '2026-02-01', 7)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    expect(options.scales.y.min).toBe(0)
    expect(options.scales.y.max).toBe(10)
  })

  it('emits select-point with the scoring_run_id when a chart point is clicked', () => {
    const points = [makePoint(11, '2026-01-01', 5), makePoint(22, '2026-02-01', 7)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    options.onClick({}, [{ index: 1 }])

    expect(wrapper.emitted('select-point')).toEqual([[22]])
  })

  it('does not emit when a click hits no point', () => {
    const points = [makePoint(11, '2026-01-01', 5), makePoint(22, '2026-02-01', 7)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    options.onClick({}, [])

    expect(wrapper.emitted('select-point')).toBeUndefined()
  })

  it('shows a visible title, also used as the chart\'s accessible name', () => {
    const points = [makePoint(1, '2026-01-01', 5), makePoint(2, '2026-02-01', 7)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    expect(wrapper.find('h2').text()).toBe('Global score history')
    expect(wrapper.findComponent({ name: 'LineStub' }).attributes('aria-labelledby')).toBe(
      'score-history-chart-title',
    )
  })

  it('offers a keyboard-operable list with one entry per audit, as a fallback to the chart', () => {
    const points = [makePoint(11, '2026-01-01', 5), makePoint(22, '2026-02-01', null)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    const buttons = wrapper.findAll('.score-history-chart__list button')
    expect(buttons).toHaveLength(2)
    expect(buttons[1]!.text()).toContain('not yet audited')
  })

  it('emits select-point when a list entry is activated', async () => {
    const points = [makePoint(11, '2026-01-01', 5), makePoint(22, '2026-02-01', 7)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    await wrapper.findAll('.score-history-chart__list button')[1]!.trigger('click')

    expect(wrapper.emitted('select-point')).toEqual([[22]])
  })

  it('defaults to the fixed 0-10 y-axis', () => {
    const points = [makePoint(1, '2026-01-01', 6.6), makePoint(2, '2026-02-01', 7.6)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    expect(options.scales.y.min).toBe(0)
    expect(options.scales.y.max).toBe(10)
  })

  it('zooms the y-axis to floor(min)-ceil(max) when the toggle is clicked', async () => {
    const points = [makePoint(1, '2026-01-01', 6.6), makePoint(2, '2026-02-01', 7.6)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    await wrapper.find('.score-history-chart__zoom-toggle').trigger('click')

    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    expect(options.scales.y.min).toBe(6)
    expect(options.scales.y.max).toBe(8)
  })

  it('toggles back to the full 0-10 scale on a second click', async () => {
    const points = [makePoint(1, '2026-01-01', 6.6), makePoint(2, '2026-02-01', 7.6)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })
    const toggle = wrapper.find('.score-history-chart__zoom-toggle')

    await toggle.trigger('click')
    await toggle.trigger('click')

    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    expect(options.scales.y.min).toBe(0)
    expect(options.scales.y.max).toBe(10)
  })

  it('falls back to the full scale when zoomed data has less than a 1-point spread', async () => {
    const points = [makePoint(1, '2026-01-01', 7), makePoint(2, '2026-02-01', 7)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    await wrapper.find('.score-history-chart__zoom-toggle').trigger('click')

    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    expect(options.scales.y.min).toBe(0)
    expect(options.scales.y.max).toBe(10)
  })

  it('ignores not-yet-audited (null) points when computing the zoomed range', async () => {
    const points = [
      makePoint(1, '2026-01-01', 6.6),
      makePoint(2, '2026-02-01', 7.6),
      makePoint(3, '2026-03-01', null),
    ]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    await wrapper.find('.score-history-chart__zoom-toggle').trigger('click')

    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    expect(options.scales.y.min).toBe(6)
    expect(options.scales.y.max).toBe(8)
  })

  it('reflects the zoom state via aria-pressed', async () => {
    const points = [makePoint(1, '2026-01-01', 6.6), makePoint(2, '2026-02-01', 7.6)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })
    const toggle = wrapper.find('.score-history-chart__zoom-toggle')

    expect(toggle.attributes('aria-pressed')).toBe('false')

    await toggle.trigger('click')

    expect(toggle.attributes('aria-pressed')).toBe('true')
  })

  it('does not show the zoom toggle when there is no meaningful history', () => {
    const wrapper = mount(ScoreHistoryChart, {
      props: { points: [makePoint(1, '2026-01-01', 7)] },
    })

    expect(wrapper.find('.score-history-chart__zoom-toggle').exists()).toBe(false)
  })
})
