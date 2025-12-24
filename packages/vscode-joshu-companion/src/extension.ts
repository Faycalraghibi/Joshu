/**
 * Joshu IDE Companion Extension
 *
 * Minimal VS Code extension that:
 * 1. Monitors editor events (open files, cursor, selection)
 * 2. Sends context updates to Python IDE server
 * 3. Handles diff proposal display
 */

import * as vscode from 'vscode';
import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

interface ServerInfo {
  port: number;
  token: string;
  workspacePath: string;
}

interface IdeContext {
  workspacePath: string;
  recentFiles: { path: string; language: string; isActive: boolean }[];
  activeFile: string | null;
  cursorPosition: { line: number; column: number } | null;
  selectedText: string;
}

let serverInfo: ServerInfo | null = null;
let recentFiles: string[] = [];
const MAX_RECENT_FILES = 10;
const MAX_SELECTED_TEXT = 16384;

export function activate(context: vscode.ExtensionContext) {
  console.log('Joshu IDE Companion activating...');

  // Find Python IDE server
  discoverServer();

  // Monitor editor events
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(onActiveEditorChange),
    vscode.window.onDidChangeTextEditorSelection(onSelectionChange),
    vscode.workspace.onDidOpenTextDocument(onDocumentOpen),
    vscode.workspace.onDidCloseTextDocument(onDocumentClose)
  );

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand('joshu.run', runJoshu),
    vscode.commands.registerCommand('joshu.sendSelection', sendSelection),
    vscode.commands.registerCommand('joshu.showStatus', showStatus),
    vscode.commands.registerCommand('joshu.acceptDiff', acceptDiff),
    vscode.commands.registerCommand('joshu.rejectDiff', rejectDiff)
  );

  // Initial context update
  updateContext();

  console.log('Joshu IDE Companion activated');
}

export function deactivate() {
  console.log('Joshu IDE Companion deactivated');
}

function discoverServer(): void {
  const tmpDir = os.tmpdir();
  try {
    const files = fs.readdirSync(tmpDir);
    for (const file of files) {
      if (file.startsWith('joshu-ide-server-') && file.endsWith('.json')) {
        try {
          const content = fs.readFileSync(path.join(tmpDir, file), 'utf-8');
          const info = JSON.parse(content) as ServerInfo;
          serverInfo = info;
          console.log(`Found Joshu IDE server on port ${info.port}`);
          return;
        } catch (e) {
          // Continue searching
        }
      }
    }
  } catch (e) {
    console.error('Error discovering server:', e);
  }
}

function sendToServer(endpoint: string, data: any): void {
  if (!serverInfo) {
    discoverServer();
    if (!serverInfo) return;
  }

  const postData = JSON.stringify(data);
  const options: http.RequestOptions = {
    hostname: '127.0.0.1',
    port: serverInfo.port,
    path: endpoint,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(postData),
      'Authorization': `Bearer ${serverInfo.token}`
    }
  };

  const req = http.request(options, (res) => {
    if (res.statusCode !== 200) {
      console.warn(`Server returned ${res.statusCode}`);
    }
  });

  req.on('error', (e) => {
    console.error('Error sending to server:', e.message);
    serverInfo = null; // Reset to trigger rediscovery
  });

  req.write(postData);
  req.end();
}

function buildContext(): IdeContext {
  const editor = vscode.window.activeTextEditor;
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

  let selectedText = '';
  let cursorPosition = null;
  let activeFile = null;

  if (editor) {
    activeFile = editor.document.uri.fsPath;
    cursorPosition = {
      line: editor.selection.active.line + 1,
      column: editor.selection.active.character + 1
    };

    if (!editor.selection.isEmpty) {
      selectedText = editor.document.getText(editor.selection);
      if (selectedText.length > MAX_SELECTED_TEXT) {
        selectedText = selectedText.substring(0, MAX_SELECTED_TEXT);
      }
    }
  }

  return {
    workspacePath: workspaceFolder?.uri.fsPath || '',
    recentFiles: recentFiles.slice(0, MAX_RECENT_FILES).map(f => ({
      path: f,
      language: '',
      isActive: f === activeFile
    })),
    activeFile,
    cursorPosition,
    selectedText
  };
}

function updateContext(): void {
  const context = buildContext();
  sendToServer('/context', context);
}

function onActiveEditorChange(editor: vscode.TextEditor | undefined): void {
  if (editor) {
    const filePath = editor.document.uri.fsPath;
    // Update recent files
    recentFiles = recentFiles.filter(f => f !== filePath);
    recentFiles.unshift(filePath);
    recentFiles = recentFiles.slice(0, MAX_RECENT_FILES);
  }
  updateContext();
}

function onSelectionChange(event: vscode.TextEditorSelectionChangeEvent): void {
  // Debounce rapid selection changes
  updateContext();
}

function onDocumentOpen(document: vscode.TextDocument): void {
  const filePath = document.uri.fsPath;
  if (!filePath.includes('extension-output')) {
    recentFiles = recentFiles.filter(f => f !== filePath);
    recentFiles.unshift(filePath);
    recentFiles = recentFiles.slice(0, MAX_RECENT_FILES);
  }
}

function onDocumentClose(document: vscode.TextDocument): void {
  // Keep in recent files even after close
}

async function runJoshu(): Promise<void> {
  const terminal = vscode.window.createTerminal('Joshu');
  terminal.show();
  terminal.sendText('joshu interactive');
}

async function sendSelection(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.selection.isEmpty) {
    vscode.window.showWarningMessage('No text selected');
    return;
  }
  updateContext();
  vscode.window.showInformationMessage('Selection sent to Joshu');
}

async function showStatus(): Promise<void> {
  if (serverInfo) {
    vscode.window.showInformationMessage(
      `Joshu IDE Server: Connected (port ${serverInfo.port})`
    );
  } else {
    discoverServer();
    if (serverInfo) {
      vscode.window.showInformationMessage(
        `Joshu IDE Server: Connected (port ${serverInfo.port})`
      );
    } else {
      vscode.window.showWarningMessage(
        'Joshu IDE Server: Not running. Start with: joshu ide start'
      );
    }
  }
}

async function acceptDiff(): Promise<void> {
  // TODO: Implement diff acceptance
  vscode.window.showInformationMessage('Diff accepted');
}

async function rejectDiff(): Promise<void> {
  // TODO: Implement diff rejection
  vscode.window.showInformationMessage('Diff rejected');
}
