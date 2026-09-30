import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import * as client from '@/api/client'
import { ApiError } from '@/api/client'
import RoadmapItemRow from '../RoadmapItemRow.vue'
import EvidencePicker from '../EvidencePicker.vue'
import type { RoadmapItemRead } from '@/api/client'

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    updateRoadmapItemStatus: vi.fn<
      (roadmapItemId: number, status: string, doneEvidenceId?: number) => Promise<void>
    >(),
  }
})

const item: RoadmapItemRead = {
  id: 1,
  improvement_task_id: 1,
  title: 'Fix it',
  description: 'a description',
  status: 'IN_PROGRESS',
  priority: 1,
  estimated_effort: null,
  estimated_impact: null,
  promoted_at: '2026-01-01',
  done_at: null,
}

describe('RoadmapItemRow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not show the evidence picker for the initial status', () => {
    const wrapper = mount(RoadmapItemRow, { props: { item } })

    expect(wrapper.findComponent(EvidencePicker).exists()).toBe(false)
  })

  it('shows the evidence picker only when the target status is DONE', async () => {
    const wrapper = mount(RoadmapItemRow, { props: { item } })

    await wrapper.find('select').setValue('DONE')

    expect(wrapper.findComponent(EvidencePicker).exists()).toBe(true)
  })

  it('disables submit for DONE until evidence is selected, then submits with done_evidence_id', async () => {
    vi.mocked(client.updateRoadmapItemStatus).mockResolvedValueOnce(undefined)
    const wrapper = mount(RoadmapItemRow, { props: { item } })
    await wrapper.find('select').setValue('DONE')

    expect(wrapper.find('button').attributes('disabled')).toBeDefined()

    wrapper.findComponent(EvidencePicker).vm.$emit('select', 42)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('button').attributes('disabled')).toBeUndefined()

    await wrapper.find('button').trigger('click')

    expect(client.updateRoadmapItemStatus).toHaveBeenCalledWith(1, 'DONE', 42)
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('submits a non-DONE transition without a done_evidence_id argument', async () => {
    vi.mocked(client.updateRoadmapItemStatus).mockResolvedValueOnce(undefined)
    const wrapper = mount(RoadmapItemRow, { props: { item } })

    await wrapper.find('select').setValue('WONT_FIX')
    await wrapper.find('button').trigger('click')

    expect(client.updateRoadmapItemStatus).toHaveBeenCalledWith(1, 'WONT_FIX')
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('shows an inline message directing to Settings on a 401', async () => {
    vi.mocked(client.updateRoadmapItemStatus).mockRejectedValueOnce(
      new ApiError(401, 'invalid or missing API key'),
    )
    const wrapper = mount(RoadmapItemRow, { props: { item } })

    await wrapper.find('select').setValue('WONT_FIX')
    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Settings')
  })
})
