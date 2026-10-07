// Stable per-browser id sent as X-Device-Id when opening a resource. The server caps how many
// new devices an account can use per month, which is what stops account sharing.
// Built from traits that survive cookie clearing and private windows; version numbers are
// stripped from the user agent so browser updates don't count as a new device.
let cached;

export async function deviceId() {
  if (cached) return cached;
  const traits = [
    navigator.userAgent.replace(/[\d._]+/g, ''),
    navigator.language,
    navigator.hardwareConcurrency,
    `${screen.width}x${screen.height}x${screen.colorDepth}`,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
  ].join('|');
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(traits));
  cached = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
  return cached;
}
