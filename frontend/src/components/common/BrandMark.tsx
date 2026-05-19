import { useState } from 'react';

type BrandMarkProps = {
  size?: number;
  className?: string;
  rounded?: boolean;
};

const BRAND_LOGO_SRC = '/assets/brand-logo.png';

export function BrandMark({ size = 40, className = '', rounded = true }: BrandMarkProps): JSX.Element {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        className={`brand-mark-fallback ${rounded ? 'rounded-2xl' : 'rounded-none'} ${className}`.trim()}
        style={{ width: size, height: size }}
        aria-label="AI标书系统"
      >
        标
      </div>
    );
  }

  return (
    <img
      src={BRAND_LOGO_SRC}
      alt="AI标书系统"
      width={size}
      height={size}
      className={`brand-mark ${rounded ? 'rounded-2xl' : 'rounded-none'} ${className}`.trim()}
      onError={() => setFailed(true)}
    />
  );
}
