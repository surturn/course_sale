export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function messageFrom(data, status) {
  const detail = data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg.replace(/^Value error, /, '')).join('. ');
  return status >= 500 ? 'The server had a problem. Try again in a moment.' : `Request failed (${status})`;
}

export async function api(path, { method = 'GET', body, form } = {}) {
  let res;
  try {
    res = await fetch(`/api/v1${path}`, {
      method,
      credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: form ?? (body ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection.");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, messageFrom(data, res.status));
  return data;
}

export const kes = (amount) => `KES ${Number(amount).toLocaleString('en-KE')}`;

// 2547XXXXXXXX -> 07XXXXXXXX for display
export const localPhone = (phone) => (phone?.startsWith('254') ? `0${phone.slice(3)}` : phone);
