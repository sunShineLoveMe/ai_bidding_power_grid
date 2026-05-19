import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Result, Space, message } from 'antd';
import { ArrowLeft, Download, RefreshCw } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { generateOnlyOfficeConfig } from '../../api/bidProject';
import { BrandMark } from '../../components/common/BrandMark';

declare global {
  interface Window {
    DocsAPI?: {
      DocEditor: new (id: string, config: Record<string, unknown>) => unknown;
    };
  }
}

const ONLYOFFICE_URL = (((import.meta as ImportMeta & { env?: Record<string, string> }).env?.VITE_ONLYOFFICE_URL) || 'http://127.0.0.1:8080').replace(/\/$/, '');

function loadOnlyOfficeScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.DocsAPI) {
      resolve();
      return;
    }
    const existing = document.querySelector<HTMLScriptElement>('script[data-onlyoffice="true"]');
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', () => reject(new Error('ONLYOFFICE 脚本加载失败')), { once: true });
      return;
    }
    const script = document.createElement('script');
    script.src = `${ONLYOFFICE_URL}/web-apps/apps/api/documents/api.js`;
    script.dataset.onlyoffice = 'true';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('ONLYOFFICE 脚本加载失败'));
    document.body.appendChild(script);
  });
}

export function OnlyOfficeEditorPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');

  const projectId = useMemo(() => searchParams.get('projectId') || '', [searchParams]);
  const sectionId = useMemo(() => searchParams.get('sectionId') || undefined, [searchParams]);
  const embedded = searchParams.get('embed') === '1';

  async function bootstrap(): Promise<void> {
    if (!projectId) {
      setError('缺少 projectId，无法打开 ONLYOFFICE 编辑器。');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError('');
    try {
      const data = await generateOnlyOfficeConfig(projectId, sectionId);
      setDownloadUrl(data.downloadUrl || '');
      await loadOnlyOfficeScript();
      const container = document.getElementById('onlyoffice-editor');
      if (!container) {
        throw new Error('ONLYOFFICE 容器未找到');
      }
      container.innerHTML = '';
      // eslint-disable-next-line no-new
      new window.DocsAPI!.DocEditor('onlyoffice-editor', data.editorConfig);
    } catch (err) {
      const reason = err instanceof Error ? err.message : String(err);
      setError(reason);
      message.error(reason);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, sectionId]);

  if (error) {
    return (
      <div className={`onlyoffice-shell ${embedded ? 'embedded' : ''}`}>
        {!embedded ? <div className="onlyoffice-topbar">
          <Space>
            <Button icon={<ArrowLeft size={16} />} onClick={() => navigate(`/bid-editor?projectId=${projectId}`)}>返回工作台</Button>
            {downloadUrl ? <Button icon={<Download size={16} />} href={downloadUrl} target="_blank">下载 DOCX</Button> : null}
          </Space>
        </div> : null}
        <Result
          status="warning"
          title="ONLYOFFICE 加载失败"
          subTitle={error}
          extra={
            <Space>
              <Button type="primary" icon={<RefreshCw size={16} />} onClick={() => void bootstrap()}>重新加载</Button>
              <Button onClick={() => navigate(`/bid-editor?projectId=${projectId}`)}>返回工作台</Button>
            </Space>
          }
        />
        <Alert
          type="info"
          showIcon
          message="检查项"
          description={`请确认 ONLYOFFICE Document Server 已运行在 ${ONLYOFFICE_URL}，并且后端 APP_PUBLIC_BASE_URL 可被容器访问。`}
        />
      </div>
    );
  }

  return (
    <div className={`onlyoffice-shell ${embedded ? 'embedded' : ''}`}>
      {!embedded ? <div className="onlyoffice-topbar">
        <Space>
          <Button icon={<ArrowLeft size={16} />} onClick={() => navigate(`/bid-editor?projectId=${projectId}`)}>返回工作台</Button>
          {downloadUrl ? <Button icon={<Download size={16} />} href={downloadUrl} target="_blank">下载 DOCX</Button> : null}
        </Space>
      </div> : null}
      {loading ? (
        <div className="onlyoffice-loading">
          <span className="brand-loading-orbit" aria-hidden="true">
            <BrandMark size={60} className="brand-loading-logo" />
          </span>
          <span>正在生成 DOCX 并加载 ONLYOFFICE 编辑器...</span>
        </div>
      ) : null}
      <div id="onlyoffice-editor" className="onlyoffice-editor" style={{ display: loading ? 'none' : 'block' }} />
    </div>
  );
}
