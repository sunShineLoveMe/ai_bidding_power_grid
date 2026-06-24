import { Image } from 'antd';
import { useEffect, useState } from 'react';
import { getAuthToken } from '../../stores/authStore';

function isProtectedAssetUrl(src?: string): boolean {
  return Boolean(src && /\/api\/knowledge\/assets\/[A-Za-z0-9-]+\/file/.test(src));
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
}

export function AuthenticatedImage({
  src,
  alt,
  className,
  fallback,
  previewSrc,
}: AuthenticatedImageProps): JSX.Element {
  const [objectUrl, setObjectUrl] = useState('');
  const [previewObjectUrl, setPreviewObjectUrl] = useState('');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const objectUrls: string[] = [];

    async function load(): Promise<void> {
      setObjectUrl('');
      setPreviewObjectUrl('');
      setFailed(false);

      try {
        if (!src) {
          setFailed(true);
          return;
        }

        const displayUrl = isProtectedAssetUrl(src) ? await fetchProtectedObjectUrl(src) : src;
        if (isProtectedAssetUrl(src)) objectUrls.push(displayUrl);
        if (cancelled) {
          objectUrls.forEach(url => URL.revokeObjectURL(url));
          return;
        }

        const fullUrl = previewSrc || src;
        const resolvedPreviewUrl = fullUrl === src
          ? displayUrl
          : isProtectedAssetUrl(fullUrl)
            ? await fetchProtectedObjectUrl(fullUrl)
            : fullUrl;
        if (resolvedPreviewUrl !== displayUrl && isProtectedAssetUrl(fullUrl)) objectUrls.push(resolvedPreviewUrl);
        if (cancelled) {
          objectUrls.forEach(url => URL.revokeObjectURL(url));
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
      objectUrls.forEach(url => URL.revokeObjectURL(url));
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
