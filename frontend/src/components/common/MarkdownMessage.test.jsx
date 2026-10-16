import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import MarkdownMessage from './MarkdownMessage';
import ExportButton from './ExportButton';

const MSG = [
  'Voici la livraison :',
  '',
  '### Jenkinsfile',
  '```groovy',
  'pipeline {',
  '  agent any',
  '}',
  '```',
  '',
  'Lancez ensuite :',
  '```bash',
  'kubectl get pods',
  '```',
  '',
  '`values.yaml` :',
  '```yaml',
  'replicaCount: 1',
  'image: x',
  'tag: y',
  '```',
  '',
  '**Dockerfile**',
  '```dockerfile',
  'FROM node:20',
  'RUN npm ci',
  'CMD ["node"]',
  '```',
].join('\n');

const countDownloadButtons = (html) => (html.match(/title="Download /g) || []).length;

describe('MarkdownMessage — bouton Download par bloc', () => {
  it('affiche Download sur chaque livrable détecté, pas sur les snippets triviaux', () => {
    const html = renderToStaticMarkup(<MarkdownMessage content={MSG} isStreaming={false} />);
    expect(countDownloadButtons(html)).toBe(3);
    expect(html).toContain('title="Download Jenkinsfile"');
    expect(html).toContain('title="Download values.yaml"');
    expect(html).toContain('title="Download Dockerfile"');
    // le one-liner kubectl reste sans bouton Download
    expect(html).toContain('kubectl');
  });

  it('masque Download pendant le streaming', () => {
    const html = renderToStaticMarkup(<MarkdownMessage content={MSG} isStreaming />);
    expect(countDownloadButtons(html)).toBe(0);
  });

  it('un message sans code ne produit aucun bouton', () => {
    const html = renderToStaticMarkup(<MarkdownMessage content={'Bonjour\n\nça va ?'} />);
    expect(countDownloadButtons(html)).toBe(0);
  });
});

describe('ExportButton — compteur de fichiers détectés', () => {
  it('affiche le nombre de fichiers détectés', () => {
    const html = renderToStaticMarkup(<ExportButton content={MSG} />);
    expect(html).toContain('(3)');
  });

  it('n’affiche pas de compteur sans fichier détecté', () => {
    const html = renderToStaticMarkup(<ExportButton content="Juste du texte" />);
    expect(html).not.toMatch(/\(\d+\)/);
  });
});
