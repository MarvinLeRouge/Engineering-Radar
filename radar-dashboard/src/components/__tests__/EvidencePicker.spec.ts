import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import * as client from '@/api/client'
import EvidencePicker from '../EvidencePicker.vue'

vi.mock('@/api/client')

describe('EvidencePicker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a message instead of a picker when there are no candidates', async () => {
    vi.mocked(client.getRoadmapItemEvidenceCandidates).mockResolvedValueOnce([])

    const wrapper = mount(EvidencePicker, { props: { roadmapItemId: 1 } })
    await flushPromises()

    expect(wrapper.find('.evidence-picker__empty').exists()).toBe(true)
    expect(wrapper.findAll('input[type="radio"]')).toHaveLength(0)
  })

  it('renders one radio per candidate and emits select on choice', async () => {
    vi.mocked(client.getRoadmapItemEvidenceCandidates).mockResolvedValueOnce([
      { id: 5, finding_id: 1, evidence_type: 'HUMAN_CONFIRMATION', content: 'fixed in PR #123', created_at: '2026-01-01' },
      { id: 6, finding_id: 1, evidence_type: 'TOOL_OUTPUT_EXCERPT', content: 'lint output', created_at: '2026-01-02' },
    ])

    const wrapper = mount(EvidencePicker, { props: { roadmapItemId: 1 } })
    await flushPromises()

    const radios = wrapper.findAll('input[type="radio"]')
    expect(radios).toHaveLength(2)

    await radios[0]!.setValue()

    expect(wrapper.emitted('select')).toEqual([[5]])
  })

  it('truncates a long content preview', async () => {
    const longContent = 'x'.repeat(200)
    vi.mocked(client.getRoadmapItemEvidenceCandidates).mockResolvedValueOnce([
      { id: 5, finding_id: 1, evidence_type: 'TOOL_OUTPUT_EXCERPT', content: longContent, created_at: '2026-01-01' },
    ])

    const wrapper = mount(EvidencePicker, { props: { roadmapItemId: 1 } })
    await flushPromises()

    expect(wrapper.text()).not.toContain(longContent)
    expect(wrapper.text()).toContain('x'.repeat(80))
  })
})
