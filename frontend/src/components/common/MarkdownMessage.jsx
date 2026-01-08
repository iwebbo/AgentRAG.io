import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';

const MarkdownMessage = ({ content, isStreaming = false }) => {
  // ✅ Buffer intelligent pour éviter le parsing de Markdown incomplet pendant le streaming
  const processedContent = useMemo(() => {
    if (!isStreaming) return content;

    // Détecte les blocs de code incomplets (``` ouvert mais pas fermé)
    const codeBlockPattern = /```(\w+)?\n/g;
    const openingMatches = [...content.matchAll(codeBlockPattern)];
    
    // Compte les blocs fermés
    const closingPattern = /```\s*$/gm;
    const closingMatches = [...content.matchAll(closingPattern)];
    
    // Si blocs de code non fermés, on ajoute une fermeture temporaire
    if (openingMatches.length > closingMatches.length) {
      return content + '\n```\n\n_Génération en cours..._';
    }

    // Détecte les listes incomplètes (ligne qui commence par - ou * mais pas terminée)
    const lastLine = content.split('\n').pop();
    if (lastLine && /^[\s]*[-*]\s*$/.test(lastLine)) {
      return content + '...';
    }

    return content;
  }, [content, isStreaming]);

  return (
    <div className="markdown-content prose prose-slate dark:prose-invert max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Rendu des blocs de code avec coloration syntaxique
          code({ node, inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '');
            const codeContent = String(children).replace(/\n$/, '');
            
            return !inline && match ? (
              <div className="relative group my-4">
                <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => navigator.clipboard.writeText(codeContent)}
                    className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-2 py-1 rounded"
                  >
                    Copier
                  </button>
                </div>
                <SyntaxHighlighter
                  style={vscDarkPlus}
                  language={match[1]}
                  PreTag="div"
                  customStyle={{
                    margin: 0,
                    borderRadius: '0.5rem',
                    fontSize: '0.875rem',
                    padding: '1rem'
                  }}
                  {...props}
                >
                  {codeContent}
                </SyntaxHighlighter>
              </div>
            ) : (
              <code 
                className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-sm font-mono text-pink-600 dark:text-pink-400" 
                {...props}
              >
                {children}
              </code>
            );
          },

          // Listes non ordonnées
          ul({ children, ...props }) {
            return (
              <ul className="list-disc pl-6 my-3 space-y-1" {...props}>
                {children}
              </ul>
            );
          },

          // Listes ordonnées
          ol({ children, ...props }) {
            return (
              <ol className="list-decimal pl-6 my-3 space-y-1" {...props}>
                {children}
              </ol>
            );
          },

          // Éléments de liste
          li({ children, ...props }) {
            return (
              <li className="leading-relaxed" {...props}>
                {children}
              </li>
            );
          },

          // Paragraphes
          p({ children, ...props }) {
            return (
              <p className="my-3 leading-relaxed" {...props}>
                {children}
              </p>
            );
          },

          // Titres
          h1({ children, ...props }) {
            return (
              <h1 className="text-3xl font-bold mt-6 mb-4 text-gray-900 dark:text-white" {...props}>
                {children}
              </h1>
            );
          },

          h2({ children, ...props }) {
            return (
              <h2 className="text-2xl font-bold mt-5 mb-3 text-gray-900 dark:text-white" {...props}>
                {children}
              </h2>
            );
          },

          h3({ children, ...props }) {
            return (
              <h3 className="text-xl font-semibold mt-4 mb-2 text-gray-900 dark:text-white" {...props}>
                {children}
              </h3>
            );
          },

          h4({ children, ...props }) {
            return (
              <h4 className="text-lg font-semibold mt-3 mb-2 text-gray-900 dark:text-white" {...props}>
                {children}
              </h4>
            );
          },

          // Citations
          blockquote({ children, ...props }) {
            return (
              <blockquote 
                className="border-l-4 border-blue-500 pl-4 py-2 my-4 italic bg-gray-50 dark:bg-gray-800/50" 
                {...props}
              >
                {children}
              </blockquote>
            );
          },

          // Liens
          a({ children, href, ...props }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 dark:text-blue-400 hover:underline"
                {...props}
              >
                {children}
              </a>
            );
          },

          // Tableaux
          table({ children, ...props }) {
            return (
              <div className="overflow-x-auto my-4">
                <table className="min-w-full border border-gray-300 dark:border-gray-700" {...props}>
                  {children}
                </table>
              </div>
            );
          },

          thead({ children, ...props }) {
            return (
              <thead className="bg-gray-100 dark:bg-gray-800" {...props}>
                {children}
              </thead>
            );
          },

          th({ children, ...props }) {
            return (
              <th className="border border-gray-300 dark:border-gray-700 px-4 py-2 text-left font-semibold" {...props}>
                {children}
              </th>
            );
          },

          td({ children, ...props }) {
            return (
              <td className="border border-gray-300 dark:border-gray-700 px-4 py-2" {...props}>
                {children}
              </td>
            );
          },

          // Séparateurs horizontaux
          hr({ ...props }) {
            return (
              <hr className="my-6 border-gray-300 dark:border-gray-700" {...props} />
            );
          },

          // Texte en gras
          strong({ children, ...props }) {
            return (
              <strong className="font-bold text-gray-900 dark:text-white" {...props}>
                {children}
              </strong>
            );
          },

          // Texte en italique
          em({ children, ...props }) {
            return (
              <em className="italic" {...props}>
                {children}
              </em>
            );
          }
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownMessage;