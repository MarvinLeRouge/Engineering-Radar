import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ScoreGauge from '../ScoreGauge.vue'

describe('ScoreGauge', () => {
  it.each([
    [9, 'score-gauge--brightgreen'],
    [8, 'score-gauge--brightgreen'],
    [7, 'score-gauge--green'],
    [6, 'score-gauge--green'],
    [5, 'score-gauge--yellow'],
    [4, 'score-gauge--yellow'],
    [3, 'score-gauge--orange'],
    [2, 'score-gauge--orange'],
    [1, 'score-gauge--red'],
    [0, 'score-gauge--red'],
  ])('renders band %s -> %s for a scored value', (value, expectedClass) => {
    const wrapper = mount(ScoreGauge, { props: { value, status: 'scored' } })

    expect(wrapper.classes()).toContain(expectedClass)
  })

  it('renders the not_applicable gray with the reason, and does not crash on a null value', () => {
    const wrapper = mount(ScoreGauge, {
      props: { value: null, status: 'not_applicable', naReason: 'no test suite exists' },
    })

    expect(wrapper.classes()).toContain('score-gauge--na')
    expect(wrapper.attributes('title')).toBe('no test suite exists')
  })

  it('renders the not_yet_audited gray, distinct from not_applicable', () => {
    const wrapper = mount(ScoreGauge, { props: { value: null, status: 'not_yet_audited' } })

    expect(wrapper.classes()).toContain('score-gauge--pending')
    expect(wrapper.classes()).not.toContain('score-gauge--na')
    expect(wrapper.attributes('title')).toBe('not yet audited')
  })

  it('toggles the reason popover on click for a non-scored gauge', async () => {
    const wrapper = mount(ScoreGauge, {
      props: { value: null, status: 'not_applicable', naReason: 'no test suite exists' },
    })

    expect(wrapper.find('.score-gauge__reason').exists()).toBe(false)

    await wrapper.trigger('click')

    expect(wrapper.find('.score-gauge__reason').text()).toBe('no test suite exists')
  })

  it('does not toggle a popover on click for a scored gauge', async () => {
    const wrapper = mount(ScoreGauge, { props: { value: 9, status: 'scored' } })

    await wrapper.trigger('click')

    expect(wrapper.find('.score-gauge__reason').exists()).toBe(false)
  })
})
