type BuildInfo = {
  app: string;
  buildId: string;
  commit: string;
  branch: string;
  builtAt: string;
};

declare global {
  interface Window {
    __AI_BID_BUILD__?: BuildInfo;
  }
}

export async function logBuildInfo(): Promise<void> {
  try {
    const response = await fetch('/build-info.json', { cache: 'no-store' });
    if (!response.ok) {
      return;
    }
    const info = (await response.json()) as BuildInfo;
    window.__AI_BID_BUILD__ = info;
    console.info(
      `[build] ${info.app} buildId=${info.buildId} commit=${info.commit} branch=${info.branch} builtAt=${info.builtAt}`,
    );
  } catch {
    // Build metadata is an operational aid; it must not block app startup.
  }
}
