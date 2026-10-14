// radar-dashboard/src/utils/__tests__/lastPointValueLabelPlugin.spec.ts
import { describe, expect, it, vi } from 'vitest'
import { lastPointValueLabelPlugin } from '../lastPointValueLabelPlugin'
import type { Chart } from 'chart.js'

interface FakeDataset {
  borderColor: string
  data: { x: number; y: number | null }[]
}

interface FakeMeta {
  data: { x: number; y: number }[]
}

function makeFakeChart(
  datasets: FakeDataset[],
  metas: FakeMeta[],
  visible: boolean[] = datasets.map(() => true),
) {
  const ctx = {
    save: vi.fn<() => void>(),
    restore: vi.fn<() => void>(),
    fillText: vi.fn<(text: string, x: number, y: number) => void>(),
    fillStyle: '',
    font: '',
    textAlign: '',
    textBaseline: '',
  }
  const chart = {
    ctx,
    data: { datasets },
    getDatasetMeta: (index: number) => metas[index],
    isDatasetVisible: (index: number) => visible[index] ?? true,
  }
  return chart as unknown as Chart<'line'> & { ctx: typeof ctx }
}

function draw(chart: Chart<'line'>): void {
  lastPointValueLabelPlugin.afterDatasetsDraw?.(chart, {} as never, { fontFamily: 'sans-serif' }, false)
}

describe('lastPointValueLabelPlugin', () => {
  it('draws the last non-null value to the right of the last point, in the line color', () => {
    const chart = makeFakeChart(
      [
        {
          borderColor: 'hsl(10, 65%, 42%)',
          data: [
            { x: 1, y: 5 },
            { x: 2, y: 7.3 },
          ],
        },
      ],
      [
        {
          data: [
            { x: 10, y: 20 },
            { x: 30, y: 15 },
          ],
        },
      ],
    )

    draw(chart)

    expect(chart.ctx.fillText).toHaveBeenCalledWith('7.3', 38, 15)
    expect(chart.ctx.fillStyle).toBe('hsl(10, 65%, 42%)')
  })

  it('falls back to the last non-null point when the most recent value is null', () => {
    const chart = makeFakeChart(
      [
        {
          borderColor: 'red',
          data: [
            { x: 1, y: 5 },
            { x: 2, y: null },
          ],
        },
      ],
      [
        {
          data: [
            { x: 10, y: 20 },
            { x: 30, y: 15 },
          ],
        },
      ],
    )

    draw(chart)

    expect(chart.ctx.fillText).toHaveBeenCalledWith('5.0', 18, 20)
  })

  it('skips a dataset with no plotted values at all', () => {
    const chart = makeFakeChart(
      [{ borderColor: 'red', data: [{ x: 1, y: null }] }],
      [{ data: [{ x: 10, y: 20 }] }],
    )

    draw(chart)

    expect(chart.ctx.fillText).not.toHaveBeenCalled()
  })

  it('skips a dataset hidden via the chart legend', () => {
    const chart = makeFakeChart(
      [{ borderColor: 'red', data: [{ x: 1, y: 5 }] }],
      [{ data: [{ x: 10, y: 20 }] }],
      [false],
    )

    draw(chart)

    expect(chart.ctx.fillText).not.toHaveBeenCalled()
  })

  it('draws one label per plotted dataset', () => {
    const chart = makeFakeChart(
      [
        { borderColor: 'red', data: [{ x: 1, y: 5 }] },
        { borderColor: 'blue', data: [{ x: 1, y: 8 }] },
      ],
      [{ data: [{ x: 10, y: 20 }] }, { data: [{ x: 10, y: 50 }] }],
    )

    draw(chart)

    expect(chart.ctx.fillText).toHaveBeenCalledTimes(2)
  })

  it('nudges a label down when two datasets end up at nearly the same height', () => {
    const chart = makeFakeChart(
      [
        { borderColor: 'red', data: [{ x: 1, y: 7 }] },
        { borderColor: 'blue', data: [{ x: 1, y: 7.1 }] },
      ],
      [{ data: [{ x: 10, y: 20 }] }, { data: [{ x: 10, y: 21 }] }],
    )

    draw(chart)

    expect(chart.ctx.fillText).toHaveBeenNthCalledWith(1, '7.0', 18, 20)
    expect(chart.ctx.fillText).toHaveBeenNthCalledWith(2, '7.1', 18, 34)
  })

  it('leaves well-separated labels at their own point height', () => {
    const chart = makeFakeChart(
      [
        { borderColor: 'red', data: [{ x: 1, y: 2 }] },
        { borderColor: 'blue', data: [{ x: 1, y: 9 }] },
      ],
      [{ data: [{ x: 10, y: 20 }] }, { data: [{ x: 10, y: 80 }] }],
    )

    draw(chart)

    expect(chart.ctx.fillText).toHaveBeenNthCalledWith(1, '2.0', 18, 20)
    expect(chart.ctx.fillText).toHaveBeenNthCalledWith(2, '9.0', 18, 80)
  })
})
