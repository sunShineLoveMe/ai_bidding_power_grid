import { Image } from 'antd';
import { useEffect, useState } from 'react';
import { getAuthToken } from '../../stores/authStore';

function isProtectedAssetUrl(src?: string): boolean {
  return Boolean(src && /\/api\/(?:bidding\/)?knowledge\/assets\/[A-Za-z0-9-]+\/file/.test(src));
}

async function fetchProtectedObjectUrl(src: string): Promise<string> {
  const token = getAuthToken();
  const response = await fetch(src, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) {
    throw new Error(`文件加载失败：${response.status}`);
  }
  return URL.createObjectURL(await response.blob());
}

type ProtectedObjectUrlCacheEntry = {
  refs: number;
  promise: Promise<string>;
  objectUrl?: string;
  revokeTimer?: number;
};

const protectedObjectUrlCache = new Map<string, ProtectedObjectUrlCacheEntry>();
const PROTECTED_OBJECT_URL_IDLE_TTL_MS = 60_000;

function acquireProtectedObjectUrl(src: string): { promise: Promise<string>; release: () => void } {
  let entry = protectedObjectUrlCache.get(src);
  if (!entry) {
    entry = {
      refs: 0,
      promise: fetchProtectedObjectUrl(src).then(objectUrl => {
        const current = protectedObjectUrlCache.get(src);
        if (current) {
          current.objectUrl = objectUrl;
        }
        return objectUrl;
      }).catch(error => {
        protectedObjectUrlCache.delete(src);
        throw error;
      }),
    };
    protectedObjectUrlCache.set(src, entry);
  }
  entry.refs += 1;
  if (entry.revokeTimer) {
    window.clearTimeout(entry.revokeTimer);
    entry.revokeTimer = undefined;
  }

  return {
    promise: entry.promise,
    release: () => {
      const current = protectedObjectUrlCache.get(src);
      if (!current) return;
      current.refs = Math.max(0, current.refs - 1);
      if (current.refs > 0 || current.revokeTimer) return;
      current.revokeTimer = window.setTimeout(() => {
        const latest = protectedObjectUrlCache.get(src);
        if (!latest || latest.refs > 0) return;
        if (latest.objectUrl) {
          URL.revokeObjectURL(latest.objectUrl);
        }
        protectedObjectUrlCache.delete(src);
      }, PROTECTED_OBJECT_URL_IDLE_TTL_MS);
    },
  };
}

export function resolveAuthenticatedDisplayUrl(src: string): { promise: Promise<string>; release: () => void } {
  if (isProtectedAssetUrl(src)) {
    return acquireProtectedObjectUrl(src);
  }
  return {
    promise: Promise.resolve(src),
    release: () => undefined,
  };
}

export async function openAuthenticatedFile(src: string): Promise<void> {
  if (!isProtectedAssetUrl(src)) {
    window.open(src, '_blank', 'noopener,noreferrer');
    return;
  }

  const objectUrl = await fetchProtectedObjectUrl(src);
  window.open(objectUrl, '_blank', 'noopener,noreferrer');
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

interface AuthenticatedImageProps {
  src?: string;
  alt?: string;
  className?: string;
  fallback?: string;
  previewSrc?: string;
  plain?: boolean;
}

export function AuthenticatedImage({
  src,
  alt,
  className,
  fallback,
  previewSrc,
  plain = false,
}: AuthenticatedImageProps): JSX.Element {
  const [objectUrl, setObjectUrl] = useState('');
  const [previewObjectUrl, setPreviewObjectUrl] = useState('');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const releases: Array<() => void> = [];

    async function load(): Promise<void> {
      setObjectUrl('');
      setPreviewObjectUrl('');
      setFailed(false);

      try {
        if (!src) {
          setFailed(true);
          return;
        }

        const displayHandle = resolveAuthenticatedDisplayUrl(src);
        releases.push(displayHandle.release);
        const displayUrl = await displayHandle.promise;
        if (cancelled) {
          return;
        }

        const fullUrl = previewSrc || src;
        let resolvedPreviewUrl = displayUrl;
        if (fullUrl !== src) {
          const previewHandle = resolveAuthenticatedDisplayUrl(fullUrl);
          releases.push(previewHandle.release);
          resolvedPreviewUrl = await previewHandle.promise;
        }
        if (cancelled) {
          return;
        }

        if (!cancelled) {
          setObjectUrl(displayUrl);
          setPreviewObjectUrl(resolvedPreviewUrl);
        }
      } catch {
        if (!cancelled) setFailed(true);
      }
    }

    load();

    return () => {
      cancelled = true;
      releases.forEach(release => release());
    };
  }, [previewSrc, src]);

  if (failed && fallback) {
    return <Image src={fallback} alt={alt || '图片'} className={className} preview={false} />;
  }

  if (failed) {
    return (
      <span className="my-3 block rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
        图片预览加载失败，请稍后重试
      </span>
    );
  }

  if (!objectUrl) {
    return (
      <span className="my-3 block rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500">
        图片加载中...
      </span>
    );
  }

  if (plain) {
    return <img src={objectUrl} alt={alt || '图片'} className={className} />;
  }

  return (
    <Image
      src={objectUrl}
      alt={alt || '图片'}
      className={className}
      preview={{ src: previewObjectUrl || objectUrl }}
      fallback={fallback}
    />
  );
}
