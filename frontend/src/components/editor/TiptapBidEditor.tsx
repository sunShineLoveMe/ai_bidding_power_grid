import { Button, Empty, Input, Modal, Select, Space, Spin, Tooltip, Typography, Upload, message } from 'antd';
import type { UploadProps } from 'antd';
import {
  Bold,
  ChevronsDown,
  ChevronsUp,
  Heading1,
  Heading2,
  Image as ImageIcon,
  Heading3,
  Italic,
  List,
  ListOrdered,
  PenLine,
  Redo2,
  Sparkles,
  Table2,
  Underline as UnderlineIcon,
  Undo2,
  UploadCloud,
  WandSparkles,
} from 'lucide-react';
import { EditorContent, JSONContent, useEditor } from '@tiptap/react';
import { mergeAttributes, Node } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Underline from '@tiptap/extension-underline';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getKnowledgeAssetSignedUrls, listKnowledgeAssets, uploadKnowledgeAsset } from '../../api/bidProject';
import type { KnowledgeAsset, KnowledgeAssetLibraryType } from '../../api/bidProject';
import { AuthenticatedImage, resolveAuthenticatedDisplayUrl } from '../common/AuthenticatedImage';

interface TiptapBidEditorProps {
  content: string;
  onChange?: (markdown: string) => void;
  placeholder?: string;
  onAiEdit?: (request: BidAiEditEditorRequest) => Promise<BidAiEditEditorResult>;
}

export type BidAiEditEditorAction = 'expand' | 'shorten' | 'polish' | 'formalize';

export interface BidAiEditEditorRequest {
  action: BidAiEditEditorAction;
  selectedText: string;
  fullContent: string;
}

export interface BidAiEditEditorResult {
  revisedText: string;
  summary?: string;
  warnings?: string[];
}

type AiPreviewState = {
  action: BidAiEditEditorAction;
  actionLabel: string;
  originalText: string;
  revisedText: string;
  summary?: string;
  warnings?: string[];
  range: { from: number; to: number };
};

type ImageDisplayUrlMap = Record<string, string>;

type ResolvedImageDisplayUrls = {
  urls: ImageDisplayUrlMap;
  releases: Array<() => void>;
};

const AI_EDIT_ACTIONS: Array<{
  action: BidAiEditEditorAction;
  label: string;
  icon: JSX.Element;
}> = [
  { action: 'expand', label: '扩写选区', icon: <ChevronsUp size={15} /> },
  { action: 'shorten', label: '缩写选区', icon: <ChevronsDown size={15} /> },
  { action: 'polish', label: '润色选区', icon: <PenLine size={15} /> },
  { action: 'formalize', label: '正式化选区', icon: <WandSparkles size={15} /> },
];

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function renderInline(value: string): string {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

function isTableSeparator(line: string): boolean {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(cell => cell.trim());
}

function normalizeImageSrc(value: string): string {
  const raw = (value || '').trim();
  if (!raw) return '';
  if (raw.startsWith('/api/')) return raw;
  try {
    const url = new URL(raw);
    if (url.pathname.startsWith('/api/')) {
      return `${url.pathname}${url.search}${url.hash}`;
    }
  } catch {
    return raw;
  }
  return raw;
}

function assetImageUrl(asset: KnowledgeAsset): string {
  return `/api/knowledge/assets/${asset.id}/file?variant=original`;
}

function isImageAsset(asset: KnowledgeAsset): boolean {
  return Boolean(asset.id) && (asset.mime_type || '').startsWith('image/');
}

function cleanUploadTitle(fileName: string): string {
  const stem = (fileName || '标书配图')
    .replace(/\.[^.]+$/, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return stem ? `泰昌${stem.replace(/^泰昌/, '')}` : '泰昌标书配图资料';
}

const BidImage = Node.create({
  name: 'bidImage',
  group: 'block',
  atom: true,
  draggable: true,
  addAttributes() {
    return {
      src: {
        default: null,
      },
      alt: {
        default: null,
      },
      title: {
        default: null,
      },
      canonicalSrc: {
        default: null,
        parseHTML: element => element.getAttribute('data-canonical-src') || element.getAttribute('src'),
        renderHTML: attributes => attributes.canonicalSrc ? { 'data-canonical-src': attributes.canonicalSrc } : {},
      },
    };
  },
  parseHTML() {
    return [{ tag: 'img[src]' }];
  },
  renderHTML({ HTMLAttributes }) {
    return ['img', mergeAttributes(HTMLAttributes, { 'data-bid-image': 'true' })];
  },
});

function markdownToHtml(markdown: string, imageDisplayUrls: ImageDisplayUrlMap = {}): string {
  const lines = (markdown || '').replace(/\r\n/g, '\n').split('\n');
  const html: string[] = [];
  let i = 0;

  const closeParagraph = (buffer: string[]) => {
    if (buffer.length) {
      html.push(`<p>${renderInline(buffer.join(' '))}</p>`);
      buffer.length = 0;
    }
  };

  const paragraph: string[] = [];

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      closeParagraph(paragraph);
      i += 1;
      continue;
    }

    if (trimmed.startsWith('|') && lines[i + 1] && isTableSeparator(lines[i + 1])) {
      closeParagraph(paragraph);
      const headers = splitTableRow(trimmed);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.push(splitTableRow(lines[i]));
        i += 1;
      }
      html.push('<table><tbody>');
      html.push(`<tr>${headers.map(cell => `<th><p>${renderInline(cell)}</p></th>`).join('')}</tr>`);
      rows.forEach(row => {
        html.push(`<tr>${row.map(cell => `<td><p>${renderInline(cell)}</p></td>`).join('')}</tr>`);
      });
      html.push('</tbody></table>');
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      closeParagraph(paragraph);
      html.push('<hr>');
      i += 1;
      continue;
    }

    const image = /^!\[(.*?)\]\((.*?)\)\s*$/.exec(trimmed);
    if (image) {
      closeParagraph(paragraph);
      const canonicalSrc = normalizeImageSrc(image[2]);
      const displaySrc = imageDisplayUrls[canonicalSrc] || canonicalSrc;
      html.push(`<img data-bid-image="true" data-canonical-src="${escapeHtml(canonicalSrc)}" src="${escapeHtml(displaySrc)}" alt="${escapeHtml(image[1] || '标书配图')}" />`);
      i += 1;
      continue;
    }

    const heading = /^(#{1,6})\s+(.+)$/.exec(trimmed);
    if (heading) {
      closeParagraph(paragraph);
      html.push(`<h${heading[1].length}>${renderInline(heading[2])}</h${heading[1].length}>`);
      i += 1;
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      closeParagraph(paragraph);
      html.push('<ul>');
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        html.push(`<li><p>${renderInline(lines[i].trim().replace(/^[-*]\s+/, ''))}</p></li>`);
        i += 1;
      }
      html.push('</ul>');
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      closeParagraph(paragraph);
      html.push('<ol>');
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        html.push(`<li><p>${renderInline(lines[i].trim().replace(/^\d+\.\s+/, ''))}</p></li>`);
        i += 1;
      }
      html.push('</ol>');
      continue;
    }

    paragraph.push(trimmed);
    i += 1;
  }

  closeParagraph(paragraph);
  return html.join('\n') || '<p></p>';
}

function textFromMarks(text: string, marks?: JSONContent['marks']): string {
  return (marks || []).reduce((current, mark) => {
    if (mark.type === 'bold') return `**${current}**`;
    if (mark.type === 'italic') return `*${current}*`;
    if (mark.type === 'code') return `\`${current}\``;
    if (mark.type === 'underline') return `<u>${current}</u>`;
    return current;
  }, text);
}

function nodeText(node?: JSONContent): string {
  if (!node) return '';
  if (node.type === 'text') return textFromMarks(node.text || '', node.marks);
  if (node.type === 'hardBreak') return '\n';
  return (node.content || []).map(nodeText).join('');
}

function listItemText(node: JSONContent): string {
  return (node.content || [])
    .map(child => (child.type === 'paragraph' ? nodeText(child) : nodeToMarkdown(child)))
    .filter(Boolean)
    .join('\n');
}

function nodeToMarkdown(node: JSONContent): string {
  if (node.type === 'heading') {
    const level = Math.min(Number(node.attrs?.level || 2), 6);
    return `${'#'.repeat(level)} ${nodeText(node)}`;
  }
  if (node.type === 'horizontalRule') {
    return '---';
  }
  if (node.type === 'paragraph') {
    return nodeText(node);
  }
  if (node.type === 'bidImage') {
    const src = normalizeImageSrc(String(node.attrs?.canonicalSrc || node.attrs?.src || ''));
    const alt = String(node.attrs?.alt || '标书配图').trim();
    return src ? `![${alt}](${src})` : '';
  }
  if (node.type === 'bulletList') {
    return (node.content || []).map(item => `- ${listItemText(item)}`).join('\n');
  }
  if (node.type === 'orderedList') {
    return (node.content || []).map((item, index) => `${index + 1}. ${listItemText(item)}`).join('\n');
  }
  if (node.type === 'blockquote') {
    return nodeText(node).split('\n').map(line => `> ${line}`).join('\n');
  }
  if (node.type === 'codeBlock') {
    return `\`\`\`\n${nodeText(node)}\n\`\`\``;
  }
  if (node.type === 'table') {
    const rows = node.content || [];
    const matrix = rows.map(row => (row.content || []).map(cell => nodeText(cell).trim()));
    if (!matrix.length) return '';
    const colCount = Math.max(...matrix.map(row => row.length));
    const normalized = matrix.map(row => [...row, ...Array(Math.max(colCount - row.length, 0)).fill('')]);
    const header = normalized[0];
    const separator = Array(colCount).fill('---');
    const body = normalized.slice(1);
    return [
      `| ${header.join(' | ')} |`,
      `| ${separator.join(' | ')} |`,
      ...body.map(row => `| ${row.join(' | ')} |`),
    ].join('\n');
  }
  return (node.content || []).map(nodeToMarkdown).filter(Boolean).join('\n\n');
}

function docToMarkdown(doc: JSONContent): string {
  return (doc.content || []).map(nodeToMarkdown).filter(Boolean).join('\n\n').trim();
}

export function TiptapBidEditor({ content, onChange, placeholder, onAiEdit }: TiptapBidEditorProps): JSX.Element {
  const lastExternalContent = useRef('');
  const lastEmittedContent = useRef('');
  const signedUrlCache = useRef<Record<string, string>>({});
  const imageDisplayReleases = useRef<Array<() => void>>([]);
  const [aiEditingAction, setAiEditingAction] = useState<BidAiEditEditorAction | null>(null);
  const [aiPreview, setAiPreview] = useState<AiPreviewState | null>(null);
  const [imageModalOpen, setImageModalOpen] = useState(false);
  const [imageLibraryType, setImageLibraryType] = useState<KnowledgeAssetLibraryType>('product');
  const [imageAssets, setImageAssets] = useState<KnowledgeAsset[]>([]);
  const [imageAssetsLoading, setImageAssetsLoading] = useState(false);
  const [imageUploadFile, setImageUploadFile] = useState<File | null>(null);
  const [imageTitle, setImageTitle] = useState('');
  const [imageUploading, setImageUploading] = useState(false);
  const extensions = useMemo(() => [
    StarterKit.configure({
      heading: { levels: [1, 2, 3, 4, 5, 6] },
    }),
    Underline,
    BidImage,
    Placeholder.configure({ placeholder: placeholder || '开始编写标书章节内容...' }),
    Table.configure({ resizable: true }),
    TableRow,
    TableHeader,
    TableCell,
  ], [placeholder]);

  const editor = useEditor({
    extensions,
    content: '<p></p>',
    editorProps: {
      attributes: {
        class: 'tiptap-bid-content',
      },
    },
    onUpdate({ editor: instance }) {
      const markdown = docToMarkdown(instance.getJSON());
      lastEmittedContent.current = markdown;
      onChange?.(markdown);
    },
  });

  const releaseCurrentImageDisplays = useCallback(() => {
    imageDisplayReleases.current.forEach(release => release());
    imageDisplayReleases.current = [];
  }, []);

  const resolveImageDisplayUrls = useCallback(async (markdown: string): Promise<ResolvedImageDisplayUrls> => {
    const ASSET_URL_RE = /\/api\/(?:bidding\/)?knowledge\/assets\/([0-9a-f-]{36})\/file[^\s)"]*/gi;
    const matches = [...(markdown || '').matchAll(ASSET_URL_RE)];
    if (!matches.length) return { urls: {}, releases: [] };
    const ids = [...new Set(matches.map(match => match[1]))];
    const uncached = ids.filter(id => !signedUrlCache.current[id]);
    if (uncached.length) {
      try {
        const fresh = await getKnowledgeAssetSignedUrls(uncached, 3600);
        Object.assign(signedUrlCache.current, fresh);
      } catch {
        // 预览签名失败时保留 canonical URL；保存和 DOCX 导出不受影响。
      }
    }
    const displayUrls: ImageDisplayUrlMap = {};
    const releases: Array<() => void> = [];
    await Promise.all(matches.map(async match => {
      const canonical = normalizeImageSrc(match[0]);
      const candidate = signedUrlCache.current[match[1]] || canonical;
      const displayHandle = resolveAuthenticatedDisplayUrl(candidate);
      releases.push(displayHandle.release);
      try {
        displayUrls[canonical] = await displayHandle.promise;
      } catch {
        displayHandle.release();
        displayUrls[canonical] = canonical;
      }
    }));
    return { urls: displayUrls, releases };
  }, []);

  useEffect(() => {
    if (!editor) return;
    const incoming = content || '';
    if (incoming === lastExternalContent.current || incoming === lastEmittedContent.current) return;
    lastExternalContent.current = incoming;
    let cancelled = false;
    let timer: number | undefined;
    resolveImageDisplayUrls(incoming).then(({ urls, releases }) => {
      if (incoming !== lastExternalContent.current) {
        releases.forEach(release => release());
        return;
      }
      timer = window.setTimeout(() => {
        if (cancelled) {
          releases.forEach(release => release());
          return;
        }
        releaseCurrentImageDisplays();
        imageDisplayReleases.current = releases;
        editor.commands.setContent(markdownToHtml(incoming, urls), false);
      }, 0);
    }).catch(() => {
      timer = window.setTimeout(() => {
        if (!cancelled) {
          editor.commands.setContent(markdownToHtml(incoming), false);
        }
      }, 0);
    });
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [content, editor, releaseCurrentImageDisplays, resolveImageDisplayUrls]);

  useEffect(() => () => {
    releaseCurrentImageDisplays();
  }, [releaseCurrentImageDisplays]);

  const applyHeading = (value: string) => {
    if (!editor) return;
    if (value === 'paragraph') {
      editor.chain().focus().setParagraph().run();
      return;
    }
    const level = Number(value.replace('heading', '')) as 1 | 2 | 3;
    editor.chain().focus().toggleHeading({ level }).run();
  };

  const requestAiEdit = async (action: BidAiEditEditorAction) => {
    if (!editor || !onAiEdit) return;
    const { from, to, empty } = editor.state.selection;
    if (empty || from === to) {
      message.warning('请先选中需要 AI 编辑的正文');
      return;
    }
    const selectedText = editor.state.doc.textBetween(from, to, '\n').trim();
    if (!selectedText) {
      message.warning('选区内没有可编辑文本');
      return;
    }
    const actionLabel = AI_EDIT_ACTIONS.find(item => item.action === action)?.label.replace('选区', '') || 'AI 编辑';
    setAiEditingAction(action);
    try {
      const result = await onAiEdit({
        action,
        selectedText,
        fullContent: docToMarkdown(editor.getJSON()),
      });
      setAiPreview({
        action,
        actionLabel,
        originalText: selectedText,
        revisedText: result.revisedText,
        summary: result.summary,
        warnings: result.warnings || [],
        range: { from, to },
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setAiEditingAction(null);
    }
  };

  const acceptAiPreview = () => {
    if (!editor || !aiPreview) return;
    editor
      .chain()
      .focus()
      .setTextSelection(aiPreview.range)
      .insertContent(markdownToHtml(aiPreview.revisedText))
      .run();
    setAiPreview(null);
    message.success('已采纳 AI 编辑结果，可用撤销按钮恢复');
  };

  const fetchImageAssets = useCallback(async () => {
    setImageAssetsLoading(true);
    try {
      const result = await listKnowledgeAssets({
        libraryType: imageLibraryType,
        page: 1,
        pageSize: 48,
      });
      setImageAssets((result.items || []).filter(isImageAsset));
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setImageAssetsLoading(false);
    }
  }, [imageLibraryType]);

  useEffect(() => {
    if (imageModalOpen) {
      void fetchImageAssets();
    }
  }, [fetchImageAssets, imageModalOpen]);

  const insertImageAsset = async (asset: KnowledgeAsset) => {
    if (!editor) return;
    const title = String(asset.metadata?.formal_caption || asset.metadata?.source_display_name || asset.title || '标书配图').trim();
    const canonicalSrc = assetImageUrl(asset);
    let displaySrc = canonicalSrc;
    let releaseDisplay: (() => void) | null = null;
    try {
      const urls = await getKnowledgeAssetSignedUrls([asset.id], 3600);
      const candidate = urls[asset.id] || canonicalSrc;
      signedUrlCache.current[asset.id] = candidate;
      const displayHandle = resolveAuthenticatedDisplayUrl(candidate);
      displaySrc = await displayHandle.promise;
      releaseDisplay = displayHandle.release;
    } catch {
      displaySrc = canonicalSrc;
    }
    if (releaseDisplay) {
      imageDisplayReleases.current.push(releaseDisplay);
    }
    editor.chain().focus().insertContent({
      type: 'bidImage',
      attrs: {
        src: displaySrc,
        canonicalSrc,
        alt: title,
        title,
      },
    }).run();
    setImageModalOpen(false);
    message.success('图片已插入正文，保存章节后将进入 DOCX 导出');
  };

  const imageUploadProps: UploadProps = {
    accept: 'image/png,image/jpeg,image/jpg,image/webp',
    maxCount: 1,
    beforeUpload(file) {
      if (!file.type.startsWith('image/')) {
        message.warning('请选择 PNG、JPG 或 WebP 图片');
        return Upload.LIST_IGNORE;
      }
      setImageUploadFile(file);
      setImageTitle(current => current || cleanUploadTitle(file.name));
      return false;
    },
    onRemove() {
      setImageUploadFile(null);
      return true;
    },
  };

  const uploadAndInsertImage = async () => {
    if (!imageUploadFile) {
      message.warning('请先选择需要插入的图片');
      return;
    }
    if (!editor) return;
    setImageUploading(true);
    try {
      const title = (imageTitle || cleanUploadTitle(imageUploadFile.name)).trim();
      const formData = new FormData();
      formData.append('file', imageUploadFile);
      formData.append('library_type', imageLibraryType);
      formData.append('asset_type', imageLibraryType === 'product' ? 'product_image' : 'qualification_image');
      formData.append('title', title);
      formData.append('category', imageLibraryType === 'product' ? '产品实物图片' : '企业证明材料');
      formData.append('evidence_type', imageLibraryType === 'product' ? 'product_image' : 'enterprise_evidence');
      formData.append('description', `${title}，用于投标文件正文配图。`);
      formData.append('tags', JSON.stringify(['标书配图']));
      formData.append('applicable_volumes', JSON.stringify(imageLibraryType === 'product' ? ['technical'] : ['business', 'qualification', 'attachment']));
      formData.append('allowed_for_bid', 'true');
      formData.append('is_sensitive', 'false');
      formData.append('anonymized', 'true');
      const asset = await uploadKnowledgeAsset(formData);
      await insertImageAsset(asset);
      setImageUploadFile(null);
      setImageTitle('');
      void fetchImageAssets();
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setImageUploading(false);
    }
  };

  return (
    <div className="tiptap-bid-editor">
      <div className="tiptap-toolbar">
        <Tooltip title="撤销"><Button size="small" icon={<Undo2 size={15} />} onClick={() => editor?.chain().focus().undo().run()} /></Tooltip>
        <Tooltip title="重做"><Button size="small" icon={<Redo2 size={15} />} onClick={() => editor?.chain().focus().redo().run()} /></Tooltip>
        <Select
          size="small"
          className="tiptap-style-select"
          value={
            editor?.isActive('heading', { level: 1 }) ? 'heading1'
              : editor?.isActive('heading', { level: 2 }) ? 'heading2'
                : editor?.isActive('heading', { level: 3 }) ? 'heading3'
                  : 'paragraph'
          }
          onChange={applyHeading}
          options={[
            { label: '正文', value: 'paragraph' },
            { label: '标题 1', value: 'heading1' },
            { label: '标题 2', value: 'heading2' },
            { label: '标题 3', value: 'heading3' },
          ]}
        />
        <Tooltip title="标题 1"><Button size="small" icon={<Heading1 size={15} />} type={editor?.isActive('heading', { level: 1 }) ? 'primary' : 'default'} onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()} /></Tooltip>
        <Tooltip title="标题 2"><Button size="small" icon={<Heading2 size={15} />} type={editor?.isActive('heading', { level: 2 }) ? 'primary' : 'default'} onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()} /></Tooltip>
        <Tooltip title="标题 3"><Button size="small" icon={<Heading3 size={15} />} type={editor?.isActive('heading', { level: 3 }) ? 'primary' : 'default'} onClick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()} /></Tooltip>
        <Tooltip title="加粗"><Button size="small" icon={<Bold size={15} />} type={editor?.isActive('bold') ? 'primary' : 'default'} onClick={() => editor?.chain().focus().toggleBold().run()} /></Tooltip>
        <Tooltip title="斜体"><Button size="small" icon={<Italic size={15} />} type={editor?.isActive('italic') ? 'primary' : 'default'} onClick={() => editor?.chain().focus().toggleItalic().run()} /></Tooltip>
        <Tooltip title="下划线"><Button size="small" icon={<UnderlineIcon size={15} />} type={editor?.isActive('underline') ? 'primary' : 'default'} onClick={() => editor?.chain().focus().toggleUnderline().run()} /></Tooltip>
        <Tooltip title="无序列表"><Button size="small" icon={<List size={15} />} type={editor?.isActive('bulletList') ? 'primary' : 'default'} onClick={() => editor?.chain().focus().toggleBulletList().run()} /></Tooltip>
        <Tooltip title="有序列表"><Button size="small" icon={<ListOrdered size={15} />} type={editor?.isActive('orderedList') ? 'primary' : 'default'} onClick={() => editor?.chain().focus().toggleOrderedList().run()} /></Tooltip>
        <Tooltip title="插入表格">
          <Button
            size="small"
            icon={<Table2 size={15} />}
            onClick={() => (editor?.chain().focus() as any).insertTable({ rows: 3, cols: 4, withHeaderRow: true }).run()}
          />
        </Tooltip>
        <Tooltip title="插入图片">
          <Button
            size="small"
            aria-label="插入图片"
            icon={<ImageIcon size={15} />}
            onClick={() => setImageModalOpen(true)}
          />
        </Tooltip>
        {onAiEdit ? (
          <>
            <span className="tiptap-toolbar-separator" />
            {AI_EDIT_ACTIONS.map(item => (
              <Tooltip key={item.action} title={item.label}>
                <Button
                  size="small"
                  aria-label={item.label}
                  icon={item.icon}
                  loading={aiEditingAction === item.action}
                  disabled={!editor || Boolean(aiEditingAction)}
                  onClick={() => void requestAiEdit(item.action)}
                />
              </Tooltip>
            ))}
          </>
        ) : null}
      </div>
      <div className="tiptap-page-scroll">
        <div className="tiptap-page">
          <EditorContent editor={editor} />
        </div>
      </div>
      <Modal
        title={aiPreview ? `${aiPreview.actionLabel}预览` : 'AI 编辑预览'}
        open={Boolean(aiPreview)}
        width={920}
        okText="采纳"
        cancelText="取消"
        onOk={acceptAiPreview}
        onCancel={() => setAiPreview(null)}
      >
        {aiPreview ? (
          <div className="ai-edit-preview">
            {aiPreview.summary ? (
              <Typography.Paragraph className="ai-edit-summary">
                <Sparkles size={15} />
                <span>{aiPreview.summary}</span>
              </Typography.Paragraph>
            ) : null}
            {aiPreview.warnings?.length ? (
              <div className="ai-edit-warnings">
                {aiPreview.warnings.map(item => <div key={item}>{item}</div>)}
              </div>
            ) : null}
            <Space align="start" size={12} className="ai-edit-columns">
              <div className="ai-edit-column">
                <strong>原文</strong>
                <pre>{aiPreview.originalText}</pre>
              </div>
              <div className="ai-edit-column ai-edit-column-result">
                <strong>编辑后</strong>
                <pre>{aiPreview.revisedText}</pre>
              </div>
            </Space>
          </div>
        ) : null}
      </Modal>
      <Modal
        title="插入标书图片"
        open={imageModalOpen}
        width={920}
        okText="上传并插入"
        cancelText="关闭"
        okButtonProps={{ loading: imageUploading, disabled: !imageUploadFile }}
        onOk={() => void uploadAndInsertImage()}
        onCancel={() => setImageModalOpen(false)}
        destroyOnHidden
      >
        <div className="editor-image-dialog">
          <div className="editor-image-dialog-head">
            <Select<KnowledgeAssetLibraryType>
              value={imageLibraryType}
              onChange={setImageLibraryType}
              options={[
                { label: '产品库图片', value: 'product' },
                { label: '资信库图片', value: 'qualification' },
              ]}
            />
            <span>优先使用已入库、可追溯的泰昌企业事实图片。</span>
          </div>
          <div className="editor-image-upload">
            <Upload {...imageUploadProps} fileList={imageUploadFile ? [{
              uid: imageUploadFile.name,
              name: imageUploadFile.name,
              status: 'done',
            }] : []}>
              <Button icon={<UploadCloud size={15} />}>选择本地图片</Button>
            </Upload>
            <Input
              value={imageTitle}
              onChange={event => setImageTitle(event.target.value)}
              placeholder="图片中文标题，例如：泰昌MPP生产线资料"
              maxLength={80}
            />
          </div>
          <div className="editor-image-library">
            <div className="editor-image-library-title">
              <strong>从资产库插入</strong>
              <Button size="small" onClick={() => void fetchImageAssets()} loading={imageAssetsLoading}>刷新</Button>
            </div>
            <Spin spinning={imageAssetsLoading}>
              {imageAssets.length ? (
                <div className="editor-image-grid">
                  {imageAssets.map(asset => (
                    <button
                      type="button"
                      key={asset.id}
                      className="editor-image-option"
                      onClick={() => void insertImageAsset(asset)}
                    >
                      <AuthenticatedImage src={assetImageUrl(asset)} alt={asset.title || '标书配图'} />
                      <span>{String(asset.metadata?.source_display_name || asset.title || '未命名图片')}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可插入图片，可先上传本地图片" />
              )}
            </Spin>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default TiptapBidEditor;
