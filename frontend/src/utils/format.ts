export function formatJson(data: unknown): string {
  if (!data) return '暂无数据';
  if (typeof data === 'string') return data;
  return JSON.stringify(data, null, 2);
}

export function formatNow(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
}
