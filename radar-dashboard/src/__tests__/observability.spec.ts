import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import type { App } from 'vue'

vi.mock('@sentry/vue', () => ({
  init: vi.fn<(options: unknown) => void>(),
  vueIntegration: vi.fn<() => { name: string }>(() => ({ name: 'vue-integration' })),
}))

import * as Sentry from '@sentry/vue'
import { initErrorTracking } from '../observability'

describe('initErrorTracking', () => {
  const app = {} as App

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('does not initialize Sentry when DSN is absent', () => {
    vi.stubEnv('VITE_SENTRY_DSN', '')

    initErrorTracking(app)

    expect(Sentry.init).not.toHaveBeenCalled()
    expect(Sentry.vueIntegration).not.toHaveBeenCalled()
  })

  it('initializes Sentry with the configured DSN and environment', () => {
    vi.stubEnv('VITE_SENTRY_DSN', ' https://example@sentry.io/123 ')
    vi.stubEnv('VITE_SENTRY_ENVIRONMENT', 'production')

    initErrorTracking(app)

    expect(Sentry.init).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        app,
        dsn: 'https://example@sentry.io/123',
        environment: 'production',
        integrations: [{ name: 'vue-integration' }],
        tracesSampleRate: 0,
      }),
    )
    expect(Sentry.vueIntegration).toHaveBeenCalledOnce()
  })

  it('defaults to development when environment is absent', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://example@sentry.io/123')
    vi.stubEnv('VITE_SENTRY_ENVIRONMENT', '')

    initErrorTracking(app)

    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({
        environment: 'development',
      }),
    )
  })

  it('disables sensitive data collection', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://example@sentry.io/123')

    initErrorTracking(app)

    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({
        dataCollection: {
          userInfo: false,
          cookies: false,
          httpHeaders: {
            request: false,
            response: false,
          },
          httpBodies: [],
          urlQueryParams: false,
          graphQL: {
            document: false,
            variables: false,
          },
          genAI: {
            inputs: false,
            outputs: false,
          },
          databaseQueryData: false,
          queues: false,
          stackFrameVariables: false,
          frameContextLines: 0,
        },
      }),
    )
  })
})
