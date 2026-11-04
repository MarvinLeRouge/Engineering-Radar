import { reactive } from 'vue'

/**
 * Track which keys of a list are expanded, for show/hide toggles.
 *
 * @returns the reactive set of expanded keys and a `toggle` that adds or removes a key
 */
export function useExpandedSet() {
  const expanded = reactive(new Set<string>())

  function toggle(key: string): void {
    if (expanded.has(key)) {
      expanded.delete(key)
    } else {
      expanded.add(key)
    }
  }

  return { expanded, toggle }
}
