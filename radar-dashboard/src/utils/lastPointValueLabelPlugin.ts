// radar-dashboard/src/utils/lastPointValueLabelPlugin.ts
import type { Plugin } from 'chart.js'

export interface LastPointValueLabelOptions {
  fontFamily: string
}

interface LinePoint {
  x: number
  y: number | null
}

// Chart.js has no built-in "value at the end of the line" label; this is the
// standard custom-plugin technique for it, kept dependency-free rather than
// pulling in chartjs-plugin-datalabels for this one use case.
export const lastPointValueLabelPlugin: Plugin<'line', LastPointValueLabelOptions> = {
  id: 'lastPointValueLabel',
  defaults: { fontFamily: 'sans-serif' },
  afterDatasetsDraw(chart, _args, options) {
    const { ctx } = chart
    const labels: { x: number; y: number; text: string; color: string }[] = []

    chart.data.datasets.forEach((dataset, datasetIndex) => {
      if (!chart.isDatasetVisible(datasetIndex)) return

      const meta = chart.getDatasetMeta(datasetIndex)
      const points = dataset.data as LinePoint[]
      let lastIndex = -1
      for (let i = points.length - 1; i >= 0; i -= 1) {
        if (points[i]?.y !== null && points[i]?.y !== undefined) {
          lastIndex = i
          break
        }
      }
      if (lastIndex === -1) return

      const element = meta.data[lastIndex]
      const value = points[lastIndex]?.y
      if (!element || value === null || value === undefined) return

      labels.push({
        x: element.x + 8,
        y: element.y,
        text: value.toFixed(1),
        color: String(dataset.borderColor ?? ctx.fillStyle),
      })
    })

    // Several metrics can be selected at once (the chart's own metric
    // selector), and their last values are routinely close together --
    // nudge labels apart vertically, top to bottom, so two close values
    // never render stacked on top of each other.
    const MIN_LABEL_GAP = 14
    labels.sort((a, b) => a.y - b.y)
    for (let i = 1; i < labels.length; i += 1) {
      const previous = labels[i - 1]!
      const current = labels[i]!
      if (current.y - previous.y < MIN_LABEL_GAP) {
        current.y = previous.y + MIN_LABEL_GAP
      }
    }

    ctx.save()
    ctx.font = `600 13px ${options.fontFamily}`
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    for (const label of labels) {
      ctx.fillStyle = label.color
      ctx.fillText(label.text, label.x, label.y)
    }
    ctx.restore()
  },
}
