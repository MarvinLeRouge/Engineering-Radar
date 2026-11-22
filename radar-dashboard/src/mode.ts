/** True in the public radar-online build (`VITE_RADAR_MODE=online`), false in the local dashboard. */
export function isOnlineMode(): boolean {
  return import.meta.env.VITE_RADAR_MODE === 'online'
}
