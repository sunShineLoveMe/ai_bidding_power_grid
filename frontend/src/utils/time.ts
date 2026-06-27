export function formatDateTime(value?: string | null, options?: Intl.DateTimeFormatOptions): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: options?.year ?? 'numeric',
    month: options?.month ?? '2-digit',
    day: options?.day ?? '2-digit',
    hour: options?.hour ?? '2-digit',
    minute: options?.minute ?? '2-digit',
    hour12: false,
    ...options,
  });
}

export function formatShortDateTime(value?: string | null): string {
  return formatDateTime(value, { year: undefined });
}
