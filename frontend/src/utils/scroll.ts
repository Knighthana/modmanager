/** Scroll a DOM element into the center of the viewport.
 *
 * Encapsulated as a standalone function so that the implementation can be
 * swapped (e.g. for Tauri) without changing call sites.
 */

export function scrollintotabitem(element: HTMLElement | null): void {
  if (!element) return
  element.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
