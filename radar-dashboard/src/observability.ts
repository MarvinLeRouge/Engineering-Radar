import type { App } from 'vue'
import * as Sentry from '@sentry/vue'

export function initErrorTracking(app: App): void {
  const sentryDsn = import.meta.env.VITE_SENTRY_DSN?.trim()

  if (!sentryDsn) {
    return
  }

  Sentry.init({
    app,
    dsn: sentryDsn,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || 'development',
    integrations: [Sentry.vueIntegration()],
    tracesSampleRate: 0,
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
  })
}
