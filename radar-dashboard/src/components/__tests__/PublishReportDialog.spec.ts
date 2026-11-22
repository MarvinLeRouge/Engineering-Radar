import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import * as client from '@/api/client'
import { ApiError } from '@/api/client'
import type { PublishPreview } from '@/api/client'
import PublishReportDialog from '../PublishReportDialog.vue'

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    getPublishPreview: vi.fn<(repositoryId: number) => Promise<PublishPreview>>(),
    publishRepository: vi.fn<(repositoryId: number) => Promise<{ report_url: string }>>(),
  }
})

// jsdom implements <dialog> but not its modal API.
const originalShowModal = HTMLDialogElement.prototype.showModal
const originalClose = HTMLDialogElement.prototype.close
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})
afterAll(() => {
  HTMLDialogElement.prototype.showModal = originalShowModal
  HTMLDialogElement.prototype.close = originalClose
})

function preview(isDirty = false): PublishPreview {
  return {
    is_dirty: isDirty,
    payload: {
      schema_version: 1,
      repository: { slug: 'summit-stats', display_name: 'Summit-Stats' },
      commit_sha: '0123456789abcdef0123456789abcdef01234567',
      scored_at: '2026-11-05T14:20:00Z',
      methodology_version: 'Quality Framework v1.0',
      global_score: 7.4,
      categories: [
        {
          name: 'Security',
          order: 4,
          weight: 1.5,
          status: 'scored',
          implemented: true,
          value: 6.2,
          confidence: 'HIGH',
        },
        {
          name: 'Performance',
          order: 6,
          weight: 1,
          status: 'not_yet_audited',
          implemented: false,
          value: null,
          confidence: null,
        },
      ],
    },
  }
}

async function openDialog() {
  const wrapper = mount(PublishReportDialog, {
    props: { repositoryId: 7 },
    attachTo: document.body,
  })
  await wrapper.find('[data-testid="publish-open"]').trigger('click')
  await flushPromises()
  return wrapper
}

describe('PublishReportDialog', () => {
  beforeEach(() => {
    vi.mocked(client.getPublishPreview).mockReset().mockResolvedValue(preview())
    vi.mocked(client.publishRepository).mockReset()
  })

  it('loads the preview of the latest run when opened', async () => {
    const wrapper = await openDialog()

    expect(client.getPublishPreview).toHaveBeenCalledWith(7)
    expect(wrapper.find('dialog').attributes('open')).toBeDefined()
    const text = wrapper.text()
    expect(text).toContain('summit-stats')
    expect(text).toContain('0123456')
    expect(text).not.toContain('0123456789abcdef0123')
    expect(text).toContain('Security')
    expect(text).toContain('Performance')
    expect(text).toContain('Not implemented yet')
    expect(text).toContain('no finding, path or note')
    wrapper.unmount()
  })

  it('does not offer to publish a dirty audit', async () => {
    vi.mocked(client.getPublishPreview).mockResolvedValue(preview(true))

    const wrapper = await openDialog()

    expect(wrapper.find('[data-testid="publish-confirm"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('uncommitted changes')
    wrapper.unmount()
  })

  it('publishes on confirmation and links to the public page', async () => {
    vi.mocked(client.publishRepository).mockResolvedValue({
      report_url: 'https://radar.example.dev/u/ada/summit-stats',
    })
    const wrapper = await openDialog()

    await wrapper.find('[data-testid="publish-confirm"]').trigger('click')
    await flushPromises()

    expect(client.publishRepository).toHaveBeenCalledWith(7)
    const link = wrapper.find('[data-testid="publish-link"]')
    expect(link.attributes('href')).toBe('https://radar.example.dev/u/ada/summit-stats')
    expect(link.attributes('target')).toBe('_blank')
    expect(wrapper.find('[data-testid="publish-confirm"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it.each([
    [401, 'invalid or missing API key', 'set it in Settings'],
    [503, 'not configured', 'RADAR_ONLINE_URL'],
    [502, 'radar-online refused the report (422): bad value', 'bad value'],
  ])('explains a %i error', async (status, detail, expected) => {
    vi.mocked(client.publishRepository).mockRejectedValue(new ApiError(status, detail))
    const wrapper = await openDialog()

    await wrapper.find('[data-testid="publish-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain(expected)
    expect(wrapper.find('[data-testid="publish-confirm"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('explains a preview that cannot be loaded', async () => {
    vi.mocked(client.getPublishPreview).mockRejectedValue(
      new ApiError(404, 'no score found for this repository'),
    )

    const wrapper = await openDialog()

    expect(wrapper.find('[role="alert"]').text()).toContain('no score found')
    expect(wrapper.find('[data-testid="publish-confirm"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('closes on cancel', async () => {
    const wrapper = await openDialog()

    await wrapper.find('[data-testid="publish-cancel"]').trigger('click')

    expect(wrapper.find('dialog').attributes('open')).toBeUndefined()
    wrapper.unmount()
  })
})
