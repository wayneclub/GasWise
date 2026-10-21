export function serviceWorkerUrl(moduleUrl: string): string {
  const bundlePath = new URL(moduleUrl).pathname
  return `/sw.js?v=${encodeURIComponent(bundlePath)}`
}
