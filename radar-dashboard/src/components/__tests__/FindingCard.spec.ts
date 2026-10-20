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

    expect(wrapper.find('.finding-card__severity').classes()).toContain(
      'finding-card__severity--high',
    )
    expect(wrapper.text()).toContain('upgrade the dependency')
  })

  it('renders no location line when the finding has no file', () => {
    const wrapper = mount(FindingCard, { props: { finding } })

    expect(wrapper.find('.finding-card__location').exists()).toBe(false)
  })

  it('renders file:line when both are present', () => {
    const withLocation = { ...finding, file: 'src/app.py', line: 42 }
    const wrapper = mount(FindingCard, { props: { finding: withLocation } })

    expect(wrapper.find('.finding-card__location').text()).toBe('src/app.py:42')
  })

  it('renders just the file when there is no line', () => {
    const withLocation = { ...finding, file: 'src/app.py', line: null }
    const wrapper = mount(FindingCard, { props: { finding: withLocation } })

    expect(wrapper.find('.finding-card__location').text()).toBe('src/app.py')
  })

  it('renders the line-only format when there is a line but no file, even with the default showFile', () => {
    const withLocation = { ...finding, file: null, line: 5 }
    const wrapper = mount(FindingCard, { props: { finding: withLocation } })

    expect(wrapper.find('.finding-card__location').text()).toBe('Line 5')
  })

  it('renders only the line, not the file, when showFile is false', () => {
    const withLocation = { ...finding, file: 'src/app.py', line: 42 }
    const wrapper = mount(FindingCard, { props: { finding: withLocation, showFile: false } })

    expect(wrapper.find('.finding-card__location').text()).toBe('Line 42')
  })

  it('renders no location line when showFile is false and there is no line', () => {
    const withLocation = { ...finding, file: 'src/app.py', line: null }
    const wrapper = mount(FindingCard, { props: { finding: withLocation, showFile: false } })

    expect(wrapper.find('.finding-card__location').exists()).toBe(false)
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
