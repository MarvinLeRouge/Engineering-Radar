import { describe, expect, it } from 'vitest'
import { extractRepositoryId, slugify } from '../slugify'

describe('slugify', () => {
  it('lowercases and hyphenates a simple name', () => {
    expect(slugify('GeoChallenge-Tracker')).toBe('geochallenge-tracker')
  })

  it('collapses runs of non-alphanumeric characters into a single hyphen', () => {
    expect(slugify('Foo   Bar_Baz.2')).toBe('foo-bar-baz-2')
  })

  it('trims leading and trailing hyphens', () => {
    expect(slugify('  leading and trailing  ')).toBe('leading-and-trailing')
  })

  it('returns an empty string for an empty input', () => {
    expect(slugify('')).toBe('')
  })
})

describe('extractRepositoryId', () => {
  it('extracts the trailing numeric id from a slug-id route param', () => {
    expect(extractRepositoryId('geochallenge-tracker-1')).toBe(1)
  })

  it('extracts a multi-digit id', () => {
    expect(extractRepositoryId('summit-stats-42')).toBe(42)
  })

  it('extracts a bare numeric id with no slug prefix', () => {
    expect(extractRepositoryId('5')).toBe(5)
  })

  it('returns null when there is no trailing numeric id', () => {
    expect(extractRepositoryId('not-a-valid-slug')).toBeNull()
  })

  it('returns null for an empty string', () => {
    expect(extractRepositoryId('')).toBeNull()
  })
})
