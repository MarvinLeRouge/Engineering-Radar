import { describe, expect, it } from 'vitest'
import { onlineRoutes } from '../online'

describe('online routes', () => {
  it('only expose the public pages', () => {
    expect(onlineRoutes.map((route) => route.path)).toEqual(['/', '/u/:user', '/u/:user/:repo'])
  })

  it('never reach a local view', () => {
    const paths = onlineRoutes.map((route) => route.path).join(' ')

    expect(paths).not.toMatch(/repositories|settings|roadmap/)
  })
})
