// radar-dashboard/src/utils/__tests__/roadmapMarkdown.spec.ts
import { describe, expect, it } from 'vitest'
import { buildRoadmapMarkdown } from '../roadmapMarkdown'
import type { RoadmapItemRead } from '@/api/client'

function makeItem(overrides: Partial<RoadmapItemRead>): RoadmapItemRead {
  return {
    id: 1,
    improvement_task_id: 1,
    title: 'Fix it',
    description: 'do the thing',
    category_name: 'Security',
    criterion_name: 'SAST findings',
    status: 'TODO',
    priority: 1,
    estimated_effort: null,
    estimated_impact: null,
    promoted_at: '2026-01-01',
    done_at: null,
    ...overrides,
  }
}

describe('buildRoadmapMarkdown', () => {
  it('starts with the title heading', () => {
    const markdown = buildRoadmapMarkdown([makeItem({})])

    expect(markdown.startsWith('# Roadmap correctif\n')).toBe(true)
  })

  it('groups items under a category H2 and a criterion H3', () => {
    const markdown = buildRoadmapMarkdown([makeItem({})])

    expect(markdown).toContain('## Security')
    expect(markdown).toContain('### SAST findings')
  })

  it('writes an unchecked checkbox with the title, and the description below it', () => {
    const markdown = buildRoadmapMarkdown([
      makeItem({ title: 'Fix it', description: 'do the thing', status: 'TODO' }),
    ])

    expect(markdown).toContain('- [ ] Fix it\n  do the thing')
  })

  it('checks the checkbox when the item is DONE', () => {
    const markdown = buildRoadmapMarkdown([makeItem({ status: 'DONE' })])

    expect(markdown).toContain('- [x] Fix it')
  })

  it('strips the criterion-name prefix from the title, since it is already the H3 heading', () => {
    const markdown = buildRoadmapMarkdown([
      makeItem({
        criterion_name: 'Code duplication',
        title: 'Code duplication: src/foo.ts',
      }),
    ])

    expect(markdown).toContain('- [ ] src/foo.ts')
    expect(markdown).not.toContain('Code duplication: src/foo.ts')
  })

  it('keeps the title as-is when it does not start with the criterion name', () => {
    const markdown = buildRoadmapMarkdown([
      makeItem({ criterion_name: 'SAST findings', title: 'SAST findings' }),
    ])

    expect(markdown).toContain('- [ ] SAST findings')
  })

  it('does not repeat the category or criterion heading for consecutive items in the same group', () => {
    const markdown = buildRoadmapMarkdown([
      makeItem({ id: 1, title: 'First' }),
      makeItem({ id: 2, title: 'Second' }),
    ])

    expect(markdown.match(/## Security/g)).toHaveLength(1)
    expect(markdown.match(/### SAST findings/g)).toHaveLength(1)
  })

  it('emits a new heading when the category or criterion changes', () => {
    const markdown = buildRoadmapMarkdown([
      makeItem({ id: 1, category_name: 'Security', criterion_name: 'SAST findings' }),
      makeItem({ id: 2, category_name: 'Testing', criterion_name: 'Coverage' }),
    ])

    expect(markdown).toContain('## Security')
    expect(markdown).toContain('## Testing')
    expect(markdown).toContain('### SAST findings')
    expect(markdown).toContain('### Coverage')
  })
})
