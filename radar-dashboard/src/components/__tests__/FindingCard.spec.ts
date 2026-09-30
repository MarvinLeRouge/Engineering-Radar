import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import * as client from '@/api/client'
import { ApiError } from '@/api/client'
import FindingCard from '../FindingCard.vue'
import type { FindingReport } from '@/api/client'

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    updateFindingVerdict: vi.fn<(findingId: number, humanVerdict: string) => Promise<void>>(),
    updateFindingStatus: vi.fn<(findingId: number, status: string) => Promise<void>>(),
  }
})

const finding: FindingReport = {
  id: 1,
  severity: 'HIGH',
  description: 'a vulnerable dependency',
  file: null,
  line: null,
  status: 'OPEN',
  human_verdict: 'UNREVIEWED',
  recommendation: 'upgrade the dependency',
}

describe('FindingCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the severity badge and the recommendation text', () => {
    const wrapper = mount(FindingCard, { props: { finding } })

    expect(wrapper.classes()).toContain('finding-card--high')
    expect(wrapper.text()).toContain('upgrade the dependency')
  })

  it('submits a verdict change and emits updated', async () => {
    vi.mocked(client.updateFindingVerdict).mockResolvedValueOnce(undefined)
    const wrapper = mount(FindingCard, { props: { finding } })

    await wrapper.find('[data-testid="verdict-select"]').setValue('TRUE_POSITIVE')

    expect(client.updateFindingVerdict).toHaveBeenCalledWith(1, 'TRUE_POSITIVE')
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('submits a status change and emits updated', async () => {
    vi.mocked(client.updateFindingStatus).mockResolvedValueOnce(undefined)
    const wrapper = mount(FindingCard, { props: { finding } })

    await wrapper.find('[data-testid="status-select"]').setValue('RESOLVED')

    expect(client.updateFindingStatus).toHaveBeenCalledWith(1, 'RESOLVED')
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('shows an inline message directing to Settings on a 401', async () => {
    vi.mocked(client.updateFindingStatus).mockRejectedValueOnce(
      new ApiError(401, 'invalid or missing API key'),
    )
    const wrapper = mount(FindingCard, { props: { finding } })

    await wrapper.find('[data-testid="status-select"]').setValue('RESOLVED')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Settings')
    expect(wrapper.emitted('updated')).toBeUndefined()
  })

  it('shows the raw error message for a non-401 failure', async () => {
    vi.mocked(client.updateFindingStatus).mockRejectedValueOnce(new Error('server exploded'))
    const wrapper = mount(FindingCard, { props: { finding } })

    await wrapper.find('[data-testid="status-select"]').setValue('RESOLVED')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('server exploded')
  })
})
