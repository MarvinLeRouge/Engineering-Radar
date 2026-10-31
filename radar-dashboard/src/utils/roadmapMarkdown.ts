import type { RoadmapItemRead } from '@/api/client'

function itemLabel(item: RoadmapItemRead): string {
  const prefix = `${item.criterion_name}: `
  return item.title.startsWith(prefix) ? item.title.slice(prefix.length) : item.title
}

export function buildRoadmapMarkdown(items: RoadmapItemRead[]): string {
  const lines: string[] = ['# Roadmap correctif', '']

  let currentCategory: string | null = null
  let currentCriterion: string | null = null

  for (const item of items) {
    if (item.category_name !== currentCategory) {
      currentCategory = item.category_name
      currentCriterion = null
      lines.push(`## ${currentCategory}`, '')
    }
    if (item.criterion_name !== currentCriterion) {
      currentCriterion = item.criterion_name
      lines.push(`### ${currentCriterion}`, '')
    }
    const checked = item.status === 'DONE' ? 'x' : ' '
    lines.push(`- [${checked}] ${itemLabel(item)}`)
    for (const descriptionLine of item.description.split('\n')) {
      lines.push(`  ${descriptionLine}`)
    }
    lines.push('')
  }

  return lines.join('\n')
}

export function downloadRoadmapMarkdown(items: RoadmapItemRead[]): void {
  const blob = new Blob([buildRoadmapMarkdown(items)], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'roadmap-corrections.md'
  link.click()
  URL.revokeObjectURL(url)
}
