type BuildInfo = {
  app: string;
  buildId: string;
  commit: string;
  branch: string;
  builtAt: string;
};

type BackendHealth = {
  status?: string;
  version?: {
    app?: string;
    commit?: string;
    branch?: string;
    builtAt?: string;
  };
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
    const healthResponse = await fetch('/api/health', { cache: 'no-store' });
    if (!healthResponse.ok) {
      return;
    }
    const health = (await healthResponse.json()) as BackendHealth;
    if (health.version) {
      console.info(
        `[build] ${health.version.app || 'ai-bidding-backend'} commit=${health.version.commit || 'unknown'} branch=${health.version.branch || 'unknown'} builtAt=${health.version.builtAt || '-'}`,
      );
    }
  } catch {
    // Build metadata is an operational aid; it must not block app startup.
  }
}
