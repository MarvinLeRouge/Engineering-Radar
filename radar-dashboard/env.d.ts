/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** `online` builds the public radar-online dashboard; anything else the local one. */
  readonly VITE_RADAR_MODE?: string
  readonly VITE_SENTRY_DSN?: string
  readonly VITE_SENTRY_ENVIRONMENT?: string
}
