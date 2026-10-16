import { describe, it, expect } from 'vitest';
import { unzipSync, strFromU8 } from 'fflate';
import {
  extractFiles,
  exportableFiles,
  sanitizePath,
  toDownloadText,
  mimeFor,
  buildZipBlob,
} from './codeBlocks';

const md = (...lines) => lines.join('\n');
const names = (markdown) => exportableFiles(extractFiles(markdown)).map((f) => f.filename);

describe('extractFiles — détection du nom', () => {
  it('reconnaît un Jenkinsfile déclaratif par le contenu', () => {
    const files = extractFiles(md('```groovy', 'pipeline {', '  agent any', '  stages { }', '}', '```'));
    expect(files).toHaveLength(1);
    expect(files[0]).toMatchObject({ filename: 'Jenkinsfile', source: 'content', kind: 'jenkinsfile', trivial: false });
  });

  it('priorité 1 : meta de la fence (title=)', () => {
    const [f] = extractFiles(md('```groovy title="vars/build.groovy"', 'def call() {', '  echo "x"', '}', '```'));
    expect(f).toMatchObject({ filename: 'vars/build.groovy', basename: 'build.groovy', source: 'meta' });
  });

  it('priorité 1 : syntaxe lang:nom et nom nu dans la meta', () => {
    expect(names(md('```yaml:values.yaml', 'a: 1', 'b: 2', 'c: 3', '```'))).toEqual(['values.yaml']);
    expect(names(md('```groovy Jenkinsfile', 'node {', '}', 'echo 1', '```'))).toEqual(['Jenkinsfile']);
  });

  it('priorité 2 : commentaire en première ligne', () => {
    const [f] = extractFiles(md('```yaml', '# values.yaml', 'replicaCount: 2', 'image: x', '```'));
    expect(f).toMatchObject({ filename: 'values.yaml', source: 'comment' });
  });

  it('ignore un shebang et un commentaire de phrase', () => {
    const [f] = extractFiles(md('```bash', '#!/bin/bash', 'set -e', 'echo a', 'echo b', 'echo c', 'echo d', '```'));
    expect(f.source).toBe('lang');
    expect(f.filename).toBe('script.sh');
    const [g] = extractFiles(md('```yaml', '# Build stage', 'a: 1', 'b: 2', 'c: 3', '```'));
    expect(g.source).toBe('lang');
  });

  it('priorité 3 : texte avant le bloc (inline code, gras, jeton connu)', () => {
    expect(names(md('Voici le `Chart.yaml` :', '', '```yaml', 'x: 1', 'y: 2', 'z: 3', '```'))).toEqual(['Chart.yaml']);
    expect(names(md('### 1. Jenkinsfile', '', '```groovy', 'a', 'b', 'c', '```'))).toEqual(['Jenkinsfile']);
    expect(names(md('**Dockerfile**', '', '```dockerfile', 'FROM node:20', 'RUN a', 'RUN b', '```'))).toEqual(['Dockerfile']);
  });

  it('rejette un nom du contexte incompatible avec le langage', () => {
    const files = extractFiles(
      md('Mettez à jour values.yaml puis lancez :', '', '```bash', 'helm upgrade a b', '```')
    );
    expect(files[0].filename).not.toBe('values.yaml');
  });

  it('priorité 4 : sniffing Dockerfile, compose, Chart, K8s, Helm, GitLab CI, GitHub Actions, pom', () => {
    expect(names(md('```', 'FROM node:20-alpine', 'WORKDIR /app', 'CMD ["node"]', '```'))).toEqual(['Dockerfile']);
    expect(names(md('```yaml', 'services:', '  db:', '    image: postgres', '```'))).toEqual(['docker-compose.yml']);
    expect(names(md('```yaml', 'apiVersion: v2', 'name: rag', 'version: 0.1.0', '```'))).toEqual(['Chart.yaml']);
    expect(names(md('```yaml', 'apiVersion: apps/v1', 'kind: Deployment', 'metadata:', '  name: a', '```'))).toEqual(['deployment.yaml']);
    expect(
      names(md('```yaml', '{{- if .Values.x }}', 'apiVersion: v1', 'kind: Service', '{{- end }}', '```'))
    ).toEqual(['templates/service.yaml']);
    expect(names(md('```yaml', 'stages:', '  - build', 'build:', '  script:', '    - make', '```'))).toEqual(['.gitlab-ci.yml']);
    expect(names(md('```yaml', 'on: [push]', 'jobs:', '  b:', '    runs-on: x', '```'))).toEqual(['.github/workflows/ci.yml']);
    expect(
      names(md('```xml', '<project>', '  <modelVersion>4.0.0</modelVersion>', '</project>', '```'))
    ).toEqual(['pom.xml']);
  });

  it('priorité 5 : nom par défaut du langage', () => {
    expect(names(md('```groovy', 'def a = 1', 'def b = 2', 'def c = 3', '```'))).toEqual(['script.groovy']);
    expect(names(md('```hcl', 'a = 1', 'b = 2', 'c = 3', '```'))).toEqual(['main.tf']);
  });
});

describe('extractFiles — blocs non livrables', () => {
  it('marque triviaux : one-liners, sorties console, langage inconnu, petits snippets shell', () => {
    const files = extractFiles(
      md(
        '```bash', 'kubectl get pods', '```',
        '```console', '$ ls', 'a', 'b', 'c', '```',
        '```', 'arbre', 'de', 'texte', '```',
        '```bash', 'a', 'b', 'c', 'd', '```'
      )
    );
    expect(files).toHaveLength(4);
    expect(files.every((f) => f.trivial)).toBe(true);
    expect(exportableFiles(files)).toHaveLength(0);
  });

  it('un one-liner avec nom explicite reste un livrable', () => {
    const [f] = extractFiles(md('```text title="VERSION.txt"', '1.2.3', '```'));
    expect(f).toMatchObject({ filename: 'VERSION.txt', trivial: false });
  });

  it('ignore les blocs vides et les entrées non-string', () => {
    expect(extractFiles('```js\n\n```')).toHaveLength(0);
    expect(extractFiles(undefined)).toHaveLength(0);
    expect(extractFiles('')).toHaveLength(0);
  });
});

describe('extractFiles — structure markdown', () => {
  it('gère les fences imbriquées (README contenant des blocs bash)', () => {
    const files = extractFiles(
      md('Voici le README.md :', '', '````markdown', '# Titre', '', '```bash', 'make build', '```', '````')
    );
    expect(files).toHaveLength(1);
    expect(files[0]).toMatchObject({ filename: 'README.md', source: 'context' });
    expect(files[0].content).toContain('```bash');
  });

  it('expose la ligne de départ du bloc (jointure avec le rendu)', () => {
    const files = extractFiles(md('intro', '', '```groovy', 'pipeline {', '}', '```'));
    expect(files[0].line).toBe(3);
  });

  it('dédoublonne uniquement entre livrables', () => {
    const files = extractFiles(
      md(
        '```bash', 'ls', '```',
        '```bash', '#!/bin/sh', 'a', 'b', '```',
        '```bash', '#!/bin/sh', 'c', 'd', '```'
      )
    );
    expect(files.map((f) => f.filename)).toEqual(['script.sh', 'script.sh', 'script-2.sh']);
  });

  it('scénario complet : pipeline + Dockerfile + chart + README', () => {
    const msg = md(
      '### Jenkinsfile',
      '```groovy',
      'pipeline {',
      '  agent any',
      '}',
      '```',
      '',
      '### Dockerfile',
      '```dockerfile',
      'FROM node:20',
      'RUN npm ci',
      'CMD ["node","a.js"]',
      '```',
      '',
      '`values.yaml` :',
      '```yaml',
      'replicaCount: 1',
      'image: x',
      'tag: y',
      '```',
      '',
      '```yaml',
      '{{- if .Values.enabled }}',
      'apiVersion: apps/v1',
      'kind: Deployment',
      '{{- end }}',
      '```',
      '',
      '### README.md',
      '```markdown',
      '# Projet',
      'texte',
      'suite',
      '```'
    );
    expect(names(msg)).toEqual([
      'Jenkinsfile',
      'Dockerfile',
      'values.yaml',
      'templates/deployment.yaml',
      'README.md',
    ]);
  });

  it('met en cache : même tableau pour un même contenu', () => {
    const m = md('```groovy', 'pipeline {', '}', '```');
    expect(extractFiles(m)).toBe(extractFiles(m));
  });
});

describe('sécurité des chemins', () => {
  it('neutralise ../, chemins absolus et caractères interdits', () => {
    expect(sanitizePath('../../etc/passwd')).toBe('etc/passwd');
    expect(sanitizePath('/abs/path/a.txt')).toBe('abs/path/a.txt');
    expect(sanitizePath('a\\b\\c.txt')).toBe('a/b/c.txt');
    expect(sanitizePath('we:ird*na?me.txt')).toBe('we_ird_na_me.txt');
    expect(sanitizePath('..')).toBeNull();
    expect(sanitizePath('')).toBeNull();
  });

  it('un nom malveillant dans la meta est assaini', () => {
    const [f] = extractFiles(md('```sh title="../../etc/cron.d/job.sh"', 'a', 'b', 'c', '```'));
    expect(f.filename).toBe('etc/cron.d/job.sh');
    expect(f.filename.includes('..')).toBe(false);
  });

  it('un nom sans extension reconnue n’est pas retenu (repli sur le langage)', () => {
    const [f] = extractFiles(md('```sh title="../../.ssh/authorized_keys"', 'a', 'b', 'c', '```'));
    expect(f.source).toBe('lang');
    expect(f.filename).toBe('script.sh');
  });
});

describe('helpers de téléchargement', () => {
  it('ajoute un retour à la ligne final une seule fois', () => {
    expect(toDownloadText('a')).toBe('a\n');
    expect(toDownloadText('a\n')).toBe('a\n');
  });

  it('choisit le mime selon le type', () => {
    expect(mimeFor('README.md')).toContain('markdown');
    expect(mimeFor('a.json')).toContain('json');
    expect(mimeFor('Jenkinsfile')).toContain('text/plain');
  });

  it('construit un zip qui conserve l’arborescence et le contenu', async () => {
    const files = exportableFiles(
      extractFiles(
        md(
          '```yaml:Chart.yaml', 'apiVersion: v2', 'name: a', 'version: 1', '```',
          '```yaml:templates/deployment.yaml', 'kind: Deployment', 'a: 1', 'b: 2', '```',
          '```yaml:templates/deployment.yaml', 'kind: Deployment', 'a: 3', 'b: 4', '```'
        )
      )
    );
    const blob = await buildZipBlob(files);
    expect(blob.type).toBe('application/zip');
    const out = unzipSync(new Uint8Array(await blob.arrayBuffer()));
    expect(Object.keys(out).sort()).toEqual([
      'Chart.yaml',
      'templates/deployment-2.yaml',
      'templates/deployment.yaml',
    ]);
    expect(strFromU8(out['Chart.yaml'])).toBe('apiVersion: v2\nname: a\nversion: 1\n');
  });
});
