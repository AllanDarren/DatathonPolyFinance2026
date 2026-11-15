// Génère src/types/generated/*.ts depuis contracts/*.schema.json (rôle A).
// Ne jamais modifier les fichiers générés à la main.
import { existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs';
import { basename, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compileFromFile } from 'json-schema-to-typescript';

const here = dirname(fileURLToPath(import.meta.url));
const contractsDir = resolve(here, '../../contracts');
const outDir = resolve(here, '../src/types/generated');

if (!existsSync(contractsDir)) {
  console.log('gen:types: contracts/ absent — on garde src/types/contracts.ts (section 8).');
  process.exit(0);
}
const schemas = readdirSync(contractsDir).filter((f) => f.endsWith('.json'));
mkdirSync(outDir, { recursive: true });
const names = [];
for (const file of schemas) {
  const ts = await compileFromFile(resolve(contractsDir, file), { cwd: contractsDir, bannerComment: '/* Généré par npm run gen:types — ne pas modifier. */' });
  const name = basename(file).replace(/\.schema\.json$|\.json$/, '');
  writeFileSync(resolve(outDir, `${name}.ts`), ts);
  names.push(name);
}
writeFileSync(resolve(outDir, 'index.ts'), names.map((n) => `export * from './${n}';`).join('\n') + '\n');
console.log(`gen:types: ${names.length} schéma(s) -> src/types/generated/`);
