/** Only allow same-site relative paths as post-login destinations. */
export function safeNext(value: string | null | undefined, fallback = "/account"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) {
    return fallback;
  }
  return value;
}

/** Login URL that returns to `next` afterwards. `save` shows the "save your results" copy. */
export function loginHref(next: string, opts: { save?: boolean; mode?: "signup" | "login" } = {}) {
  const params = new URLSearchParams({ next });
  if (opts.save) params.set("reason", "save");
  if (opts.mode) params.set("mode", opts.mode);
  return `/login?${params}`;
}
