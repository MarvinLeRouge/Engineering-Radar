import { describe, expect, it } from 'vitest'
import { useExpandedSet } from '../useExpandedSet'

describe('useExpandedSet', () => {
  it('starts with nothing expanded', () => {
    const { expanded } = useExpandedSet()
    expect(expanded.size).toBe(0)
  })

  it('expands a key on the first toggle and collapses it on the second', () => {
    const { expanded, toggle } = useExpandedSet()
    toggle('HIGH')
    expect(expanded.has('HIGH')).toBe(true)
    toggle('HIGH')
    expect(expanded.has('HIGH')).toBe(false)
  })

  it('keeps keys independent', () => {
    const { expanded, toggle } = useExpandedSet()
    toggle('HIGH')
    toggle('LOW')
    toggle('HIGH')
    expect([...expanded]).toEqual(['LOW'])
  })
})
