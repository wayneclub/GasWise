export function safeProductLink(value: string | null | undefined): string | null {
  try {
    const url = new URL(value ?? '')
    const hosts = ['amazon.com', 'autozone.com', 'oreillyauto.com', 'mann-filter.com', 'boschautoparts.com']
    return url.protocol === 'https:' && !url.username && !url.password && hosts.some((h) => url.hostname === h || url.hostname.endsWith(`.${h}`)) ? url.toString() : null
  } catch { return null }
}
export function isAmazonProduct(value: string) {
  try { const url = new URL(value); return url.protocol === 'https:' && ['amazon.com', 'www.amazon.com'].includes(url.hostname) && /\/(dp|gp\/product)\/[A-Z0-9]{10}(?:\/|$)/i.test(url.pathname) && !url.username && !url.password } catch { return false }
}
