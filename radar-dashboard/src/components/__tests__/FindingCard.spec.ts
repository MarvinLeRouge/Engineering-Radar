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
    updateFindingNote: vi.fn<(findingId: number, note: string) => Promise<void>>(),
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
  verdict_note: null,
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

  describe('verdict note', () => {
    it('is hidden while the finding is open and unreviewed', () => {
      const wrapper = mount(FindingCard, { props: { finding } })

      expect(wrapper.find('[data-testid="verdict-note"]').exists()).toBe(false)
    })

    it.each([{ human_verdict: 'FALSE_POSITIVE' }, { status: 'WONT_FIX' }, { status: 'RESOLVED' }])(
      'appears with its current text once the finding is dismissed (%o)',
      (dismissed) => {
        const wrapper = mount(FindingCard, {
          props: { finding: { ...finding, ...dismissed, verdict_note: 'kept' } },
        })

        const input = wrapper.find<HTMLInputElement>('[data-testid="verdict-note"]')
        expect(input.element.value).toBe('kept')
        expect(input.attributes('maxlength')).toBe('200')
      },
    )

    it('offers the preset reasons through a datalist and explains it to assistive tech', () => {
      const wrapper = mount(FindingCard, {
        props: { finding: { ...finding, status: 'WONT_FIX' } },
      })

      const input = wrapper.find('[data-testid="verdict-note"]')
      const list = wrapper.find(`datalist#${input.attributes('list')}`)
      expect(list.findAll('option').map((o) => o.attributes('value'))).toEqual([
        'Waiting for an upstream fix',
        'Framework convention, used at runtime',
        'Accepted risk, local-only image',
      ])
      const hint = wrapper.find(`#${input.attributes('aria-describedby')}`)
      expect(hint.text()).toContain('start typing')
    })

    it('saves the note when it changes, then reports the update', async () => {
      vi.mocked(client.updateFindingNote).mockResolvedValue(undefined)
      const wrapper = mount(FindingCard, {
        props: { finding: { ...finding, human_verdict: 'FALSE_POSITIVE' } },
      })

      const input = wrapper.find('[data-testid="verdict-note"]')
      // setValue fires both input and change, like a user committing the field.
      await input.setValue('Framework convention, used at runtime')
      await Promise.resolve()

      expect(client.updateFindingNote).toHaveBeenCalledExactlyOnceWith(
        1,
        'Framework convention, used at runtime',
      )
      expect(wrapper.emitted('updated')).toHaveLength(1)
    })

    it('shows the API error when saving the note fails', async () => {
      vi.mocked(client.updateFindingNote).mockRejectedValue(new ApiError(401, 'unauthorized'))
      const wrapper = mount(FindingCard, {
        props: { finding: { ...finding, human_verdict: 'FALSE_POSITIVE' } },
      })

      await wrapper.find('[data-testid="verdict-note"]').trigger('change')
      await Promise.resolve()
      await Promise.resolve()

      expect(wrapper.find('.finding-card__error').text()).toContain('Missing or invalid API key')
    })
  })
})
