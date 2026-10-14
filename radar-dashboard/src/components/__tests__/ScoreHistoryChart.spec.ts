import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ScoreHistoryChart from '../ScoreHistoryChart.vue'
import type { CategoryScorePoint, ScoreHistoryPoint } from '@/api/client'
import { lastPointValueLabelPlugin } from '@/utils/lastPointValueLabelPlugin'

// Mocked solely because jsdom has no real <canvas> 2D context (Chart.js
// would throw on getContext); this is a narrow exception for the charting
// library's own rendering internals, not a general mocking precedent -- the
// rest of this codebase deliberately invokes real code/tools in tests.
vi.mock('vue-chartjs', () => ({
  Line: {
    name: 'LineStub',
    props: ['data', 'options', 'plugins'],
    template: '<div />',
  },
}))

function makePoint(
  id: number,
  scoredAt: string,
  globalScore: number | null,
  categories: CategoryScorePoint[] = [],
): ScoreHistoryPoint {
  return {
    scoring_run_id: id,
    audit_id: id,
    commit_sha: 'a'.repeat(40),
    scored_at: scoredAt,
    global_score: globalScore,
    categories,
  }
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

  it('passes the last-point value label plugin to the chart, scoped to this instance', () => {
    const points = [makePoint(1, '2026-01-01', 5), makePoint(2, '2026-02-01', 7)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    const plugins = wrapper.findComponent({ name: 'LineStub' }).props('plugins')
    expect(plugins).toContain(lastPointValueLabelPlugin)
  })

  it('reserves right-side padding so the last-point value label is not clipped', () => {
    const points = [makePoint(1, '2026-01-01', 5), makePoint(2, '2026-02-01', 7)]
    const wrapper = mount(ScoreHistoryChart, { props: { points } })

    const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
    expect(options.layout.padding.right).toBeGreaterThan(0)
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

  describe('metric selector and drill-down', () => {
    function pointsWithCategories(): ScoreHistoryPoint[] {
      return [
        makePoint(1, '2026-01-01', 5, [
          { id: 10, name: 'Security', value: 4 },
          { id: 20, name: 'Architecture', value: 6 },
        ]),
        makePoint(2, '2026-02-01', 7, [
          { id: 10, name: 'Security', value: 8 },
          { id: 20, name: 'Architecture', value: 7 },
        ]),
      ]
    }

    it('does not show the metric selector when the history has no categories', () => {
      const points = [makePoint(1, '2026-01-01', 5), makePoint(2, '2026-02-01', 7)]
      const wrapper = mount(ScoreHistoryChart, { props: { points } })

      expect(wrapper.find('.score-history-chart__metrics').exists()).toBe(false)
    })

    it('shows one chip per metric, Global selected by default', () => {
      const wrapper = mount(ScoreHistoryChart, { props: { points: pointsWithCategories() } })

      const chips = wrapper.findAll('.score-history-chart__metric-toggle')
      expect(chips.map((chip) => chip.text())).toEqual(['Global score', 'Security', 'Architecture'])
      expect(chips[0]!.attributes('aria-pressed')).toBe('true')
      expect(chips[1]!.attributes('aria-pressed')).toBe('false')
      expect(chips[2]!.attributes('aria-pressed')).toBe('false')
    })

    it('plots only the Global score dataset by default', () => {
      const wrapper = mount(ScoreHistoryChart, { props: { points: pointsWithCategories() } })

      const data = wrapper.findComponent({ name: 'LineStub' }).props('data')
      expect(data.datasets).toHaveLength(1)
      expect(data.datasets[0].label).toBe('Global score')
    })

    it('adds a category dataset when its chip is toggled on', async () => {
      const wrapper = mount(ScoreHistoryChart, { props: { points: pointsWithCategories() } })

      await wrapper.findAll('.score-history-chart__metric-toggle')[1]!.trigger('click')

      const data = wrapper.findComponent({ name: 'LineStub' }).props('data')
      expect(data.datasets.map((d: { label: string }) => d.label)).toEqual([
        'Global score',
        'Security',
      ])
      expect(data.datasets[1].data).toEqual([
        { x: new Date('2026-01-01').getTime(), y: 4 },
        { x: new Date('2026-02-01').getTime(), y: 8 },
      ])
    })

    it('does not allow deselecting the last remaining metric', async () => {
      const wrapper = mount(ScoreHistoryChart, { props: { points: pointsWithCategories() } })
      const globalChip = wrapper.findAll('.score-history-chart__metric-toggle')[0]!

      await globalChip.trigger('click')

      expect(globalChip.attributes('aria-pressed')).toBe('true')
      const data = wrapper.findComponent({ name: 'LineStub' }).props('data')
      expect(data.datasets).toHaveLength(1)
    })

    it('drills down into a single category: title, back link, and global deselected', async () => {
      const wrapper = mount(ScoreHistoryChart, { props: { points: pointsWithCategories() } })
      const [globalChip, securityChip] = wrapper.findAll('.score-history-chart__metric-toggle')

      await securityChip!.trigger('click')
      await globalChip!.trigger('click')

      expect(wrapper.find('h2').text()).toBe('Security')
      expect(wrapper.find('.score-history-chart__back').exists()).toBe(true)
      const data = wrapper.findComponent({ name: 'LineStub' }).props('data')
      expect(data.datasets.map((d: { label: string }) => d.label)).toEqual(['Security'])
    })

    it('returns to the global overview when "Back to overview" is clicked', async () => {
      const wrapper = mount(ScoreHistoryChart, { props: { points: pointsWithCategories() } })
      const [globalChip, securityChip] = wrapper.findAll('.score-history-chart__metric-toggle')
      await securityChip!.trigger('click')
      await globalChip!.trigger('click')

      await wrapper.find('.score-history-chart__back').trigger('click')

      expect(wrapper.find('h2').text()).toBe('Global score history')
      expect(wrapper.find('.score-history-chart__back').exists()).toBe(false)
      const chips = wrapper.findAll('.score-history-chart__metric-toggle')
      expect(chips[0]!.attributes('aria-pressed')).toBe('true')
      expect(chips[1]!.attributes('aria-pressed')).toBe('false')
    })

    it('zooms using only the values of the currently selected metrics', async () => {
      const wrapper = mount(ScoreHistoryChart, { props: { points: pointsWithCategories() } })
      const [globalChip, securityChip] = wrapper.findAll('.score-history-chart__metric-toggle')
      await securityChip!.trigger('click')
      await globalChip!.trigger('click')

      await wrapper.find('.score-history-chart__zoom-toggle').trigger('click')

      const options = wrapper.findComponent({ name: 'LineStub' }).props('options')
      // Security alone ranges 4-8, not Global's 5-7.
      expect(options.scales.y.min).toBe(4)
      expect(options.scales.y.max).toBe(8)
    })

    it('marks the metric selector as an accessible toggle-button group', () => {
      const wrapper = mount(ScoreHistoryChart, { props: { points: pointsWithCategories() } })

      const group = wrapper.find('[role="group"]')
      expect(group.exists()).toBe(true)
      expect(group.attributes('aria-label')).toBe('Metrics to display')
    })

    it('shows a title and no back link when two categories are compared with Global off', async () => {
      const wrapper = mount(ScoreHistoryChart, { props: { points: pointsWithCategories() } })
      const [globalChip, securityChip, architectureChip] = wrapper.findAll(
        '.score-history-chart__metric-toggle',
      )
      await securityChip!.trigger('click')
      await architectureChip!.trigger('click')
      await globalChip!.trigger('click')

      expect(wrapper.find('h2').text()).toBe('Score history')
      expect(wrapper.find('.score-history-chart__back').exists()).toBe(false)
      const data = wrapper.findComponent({ name: 'LineStub' }).props('data')
      expect(data.datasets.map((d: { label: string }) => d.label)).toEqual([
        'Security',
        'Architecture',
      ])
    })

    it('moves focus to the title when "Back to overview" is clicked', async () => {
      const wrapper = mount(ScoreHistoryChart, {
        props: { points: pointsWithCategories() },
        attachTo: document.body,
      })
      const [globalChip, securityChip] = wrapper.findAll('.score-history-chart__metric-toggle')
      await securityChip!.trigger('click')
      await globalChip!.trigger('click')

      await wrapper.find('.score-history-chart__back').trigger('click')

      expect(document.activeElement).toBe(wrapper.find('h2').element)
      wrapper.unmount()
    })

    it('gives every category a distinct line color, even past 7 categories', async () => {
      const categories = Array.from({ length: 9 }, (_, i) => ({
        id: i + 1,
        name: `Category ${i + 1}`,
        value: i,
      }))
      const points = [
        makePoint(1, '2026-01-01', 5, categories),
        makePoint(2, '2026-02-01', 6, categories),
      ]
      const wrapper = mount(ScoreHistoryChart, { props: { points } })

      // Select every chip (skip index 0, Global, already selected).
      for (const chip of wrapper.findAll('.score-history-chart__metric-toggle').slice(1)) {
        await chip.trigger('click')
      }

      const data = wrapper.findComponent({ name: 'LineStub' }).props('data')
      const colors = data.datasets.map((d: { borderColor: string }) => d.borderColor)
      expect(new Set(colors).size).toBe(colors.length)
    })

    it('keeps a category line color stable across toggling other metrics', async () => {
      const wrapper = mount(ScoreHistoryChart, { props: { points: pointsWithCategories() } })
      const [, securityChip, architectureChip] = wrapper.findAll(
        '.score-history-chart__metric-toggle',
      )

      await securityChip!.trigger('click')
      const firstPass = wrapper.findComponent({ name: 'LineStub' }).props('data')
      const securityColor = firstPass.datasets.find(
        (d: { label: string }) => d.label === 'Security',
      ).borderColor

      await architectureChip!.trigger('click')
      await securityChip!.trigger('click')
      await securityChip!.trigger('click')
      const secondPass = wrapper.findComponent({ name: 'LineStub' }).props('data')
      const securityColorAgain = secondPass.datasets.find(
        (d: { label: string }) => d.label === 'Security',
      ).borderColor

      expect(securityColorAgain).toBe(securityColor)
    })

    it('shows the chart legend only once more than one metric is plotted', async () => {
      const wrapper = mount(ScoreHistoryChart, { props: { points: pointsWithCategories() } })
      const [, securityChip] = wrapper.findAll('.score-history-chart__metric-toggle')

      expect(wrapper.findComponent({ name: 'LineStub' }).props('options').plugins.legend.display).toBe(
        false,
      )

      await securityChip!.trigger('click')

      expect(wrapper.findComponent({ name: 'LineStub' }).props('options').plugins.legend.display).toBe(
        true,
      )
    })
  })
})
