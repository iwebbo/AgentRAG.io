import { createContext, memo, useContext, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import { useExport } from '../../hooks/useExport';
import { exportableFiles, extractFiles } from '../../utils/codeBlocks';

// Fichiers détectés dans le message, indexés par ligne de départ du bloc.
// `null` pendant le streaming : le bouton Download n'apparaît qu'une fois le message terminé.
// Un contexte (et non des props) car COMPONENTS est statique : identité stable → pas de remount.
const FilesContext = createContext(null);

const CodeBlock = ({ language, code, line }) => {
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);
  const filesByLine = useContext(FilesContext);
  const { exportFile } = useExport();

  const file = filesByLine && line ? filesByLine.get(line) : null;
  const canDownload = !!file && !file.trivial;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (_) {
      /* clipboard indisponible (contexte non sécurisé) */
    }
  };

  const download = async () => {
    try {
      await exportFile(file);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (_) {
      /* erreur déjà tracée par le hook */
    }
  };

  return (
    <div className="code-block">
      <div className="code-block-head">
        <span>
          {language || 'text'}
          {canDownload && <span style={{ opacity: 0.6, marginLeft: 8 }}>{file.filename}</span>}
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {canDownload && (
            <button
              type="button"
              className="code-block-copy"
              onClick={download}
              title={`Download ${file.basename}`}
            >
              {saved ? 'Saved' : 'Download'}
            </button>
          )}
          <button type="button" className="code-block-copy" onClick={copy}>
            {copied ? 'Copied' : 'Copy'}
          </button>
        </span>
      </div>
      <SyntaxHighlighter
        style={vscDarkPlus}
        language={language || 'text'}
        PreTag="div"
        customStyle={{ margin: 0, padding: '12px 14px', background: 'transparent', fontSize: '12.5px' }}
        codeTagProps={{ style: { fontFamily: 'var(--font-mono)' } }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
};

// Les composants sont définis hors du rendu : identité stable → pas de remount pendant le streaming.
const COMPONENTS = {
  // react-markdown v9 ne fournit plus `inline` : un bloc = langage déclaré ou contenu multi-lignes.
  code({ className, children, node, ...props }) {
    const match = /language-([\w-]+)/.exec(className || '');
    const raw = String(children);
    const isBlock = !!match || raw.includes('\n');
    if (!isBlock) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }
    return (
      <CodeBlock
        language={match ? match[1] : ''}
        code={raw.replace(/\n$/, '')}
        line={node?.position?.start?.line}
      />
    );
  },
  // Le bloc de code gère déjà son propre conteneur : on évite <pre><div>.
  pre({ children }) {
    return <>{children}</>;
  },
  table({ children }) {
    return (
      <div className="md-table-wrap">
        <table>{children}</table>
      </div>
    );
  },
  a({ children, href }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  },
};

const REMARK_PLUGINS = [remarkGfm];

const MarkdownMessage = ({ content = '', isStreaming = false }) => {
  // Pendant le streaming, ferme temporairement un bloc ``` ouvert pour éviter un rendu cassé.
  const processedContent = useMemo(() => {
    if (!isStreaming) return content;

    const fences = (content.match(/^\s*```/gm) || []).length;
    if (fences % 2 === 1) {
      return `${content}\n\`\`\`\n\n_Génération en cours..._`;
    }

    const lastLine = content.split('\n').pop();
    if (lastLine && /^\s*[-*]\s*$/.test(lastLine)) {
      return `${content}...`;
    }
    return content;
  }, [content, isStreaming]);

  // Détection des fichiers livrables : uniquement sur un message terminé (content === processedContent,
  // donc les numéros de ligne concordent avec ceux du rendu). Résultat mis en cache par contenu.
  const filesByLine = useMemo(() => {
    if (isStreaming || !content || !content.includes('\n')) return null;
    const files = exportableFiles(extractFiles(content));
    return files.length ? new Map(files.map((f) => [f.line, f])) : null;
  }, [content, isStreaming]);

  return (
    <div className="markdown-content">
      <FilesContext.Provider value={filesByLine}>
        <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={COMPONENTS}>
          {processedContent}
        </ReactMarkdown>
      </FilesContext.Provider>
    </div>
  );
};

export default memo(MarkdownMessage);
