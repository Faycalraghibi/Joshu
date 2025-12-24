/**
 * esbuild configuration for VS Code extension
 */

const esbuild = require('esbuild');

const watch = process.argv.includes('--watch');

async function build() {
  const context = await esbuild.context({
    entryPoints: ['src/extension.ts'],
    bundle: true,
    outfile: 'dist/extension.js',
    platform: 'node',
    target: 'node16',
    format: 'cjs',
    external: ['vscode'],
    sourcemap: true,
    minify: !watch,
  });

  if (watch) {
    console.log('Watching for changes...');
    await context.watch();
  } else {
    await context.rebuild();
    await context.dispose();
    console.log('Build complete');
  }
}

build().catch(console.error);
