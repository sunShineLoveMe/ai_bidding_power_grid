import { Button, Select, Tooltip } from 'antd';
import {
  Bold,
  Heading1,
  Heading2,
  Heading3,
  Italic,
  List,
  ListOrdered,
  Redo2,
  Table2,
  Underline as UnderlineIcon,
  Undo2,
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
import { getKnowledgeAssetSignedUrls } from '../../api/bidProject';

interface TiptapBidEditorProps {
  content: string;
  onChange?: (markdown: string) => void;
  placeholder?: string;
}

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
    };
  },
  parseHTML() {
    return [{ tag: 'img[src]' }];
  },
  renderHTML({ HTMLAttributes }) {
    return ['img', mergeAttributes(HTMLAttributes, { 'data-bid-image': 'true' })];
  },
});

function markdownToHtml(markdown: string): string {
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
      html.push(`<img data-bid-image="true" src="${escapeHtml(normalizeImageSrc(image[2]))}" alt="${escapeHtml(image[1] || '标书配图')}" />`);
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
    const src = normalizeImageSrc(String(node.attrs?.src || ''));
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

export function TiptapBidEditor({ content, onChange, placeholder }: TiptapBidEditorProps): JSX.Element {
  const lastExternalContent = useRef(content || '');
  const lastEmittedContent = useRef(content || '');
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
    content: markdownToHtml(content || ''),
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

  // 签名 URL 缓存：key = asset_id，value = 签名 URL（有效期 1 小时）
  const signedUrlCache = useRef<Record<string, string>>({});

  /**
   * 从 markdown 内容中提取所有 /api/bidding/knowledge/assets/<id>/file 格式的图片 URL，
   * 批量换成 Supabase Storage 签名 URL，让浏览器直连 CDN，不再经过后端中转。
   */
  const resolveSignedUrls = useCallback(async (markdown: string): Promise<string> => {
    const ASSET_URL_RE = /\/api\/(?:bidding\/)?knowledge\/assets\/([0-9a-f-]{36})\/file[^\s)"]*/gi;
    const matches = [...markdown.matchAll(ASSET_URL_RE)];
    if (!matches.length) return markdown;

    // 找出尚未缓存的 asset_id
    const uncachedIds = [...new Set(matches.map(m => m[1]))].filter(
      id => !signedUrlCache.current[id],
    );

    if (uncachedIds.length) {
      try {
        const fresh = await getKnowledgeAssetSignedUrls(uncachedIds, 3600);
        Object.assign(signedUrlCache.current, fresh);
      } catch {
        // 签名 URL 获取失败时降级：保留原 /api/ 路径，不影响渲染
      }
    }

    // 替换 markdown 中的图片 URL
    return markdown.replace(ASSET_URL_RE, (original, assetId: string) => {
      return signedUrlCache.current[assetId] || original;
    });
  }, []);

  useEffect(() => {
    if (!editor) return;
    const incoming = content || '';
    if (incoming === lastExternalContent.current || incoming === lastEmittedContent.current) return;
    lastExternalContent.current = incoming;

    // 先尝试替换签名 URL，再渲染到编辑器
    resolveSignedUrls(incoming).then(resolved => {
      // 如果在异步期间 content 已经变化，放弃本次更新
      if (incoming !== lastExternalContent.current) return;
      editor.commands.setContent(markdownToHtml(resolved), false);
    }).catch(() => {
      // 降级：直接用原始 markdown 渲染
      editor.commands.setContent(markdownToHtml(incoming), false);
    });
  }, [content, editor, resolveSignedUrls]);

  const applyHeading = (value: string) => {
    if (!editor) return;
    if (value === 'paragraph') {
      editor.chain().focus().setParagraph().run();
      return;
    }
    const level = Number(value.replace('heading', '')) as 1 | 2 | 3;
    editor.chain().focus().toggleHeading({ level }).run();
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
      </div>
      <div className="tiptap-page-scroll">
        <div className="tiptap-page">
          <EditorContent editor={editor} />
        </div>
      </div>
    </div>
  );
}

export default TiptapBidEditor;
