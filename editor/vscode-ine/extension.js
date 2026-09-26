"use strict";

const vscode = require("vscode");
const { spawn } = require("child_process");
const path = require("path");

const KIND_OF = {
  kind: vscode.CompletionItemKind.Keyword,
  property: vscode.CompletionItemKind.Property,
  concept: vscode.CompletionItemKind.Class,
  parent: vscode.CompletionItemKind.Module,
};

// Trigger on a space (contexts like `make `, `header `, `inside `) and on
// letters so `make h` asks the dictionary while the word is still being
// typed. No Ine vocabulary here: these are generic characters.
const TRIGGER_CHARS = [
  " ",
  ..."abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
];

// A hover is a glance, not a document: show a handful of suggestions and
// say how many were left out rather than dropping them silently.
const HOVER_ITEM_LIMIT = 12;

// Diagnostics wait for a pause in typing; one validate per keystroke would
// queue a query per character through the single worker.
const DIAGNOSTIC_DELAY_MS = 200;

const diagnostics = vscode.languages.createDiagnosticCollection("ine");

// One pending refresh per document, so a fast typist supersedes their own
// in-flight request instead of queueing behind it.
const diagnosticTimers = new Map();

function pythonTarget(root) {
  return {
    exe: process.env.INE_PYTHON || "python",
    args: [path.join(root, "src", "ine", "autocomplete.py")],
    cwd: root,
  };
}

// One long-lived python process answering JSON-lines queries. Requests are
// serialized (FIFO) and matched in order; a process that dies respawns on
// the next query, so a stale keystroke never permanently breaks completion.
class DictionaryWorker {
  constructor(root) {
    this.target = pythonTarget(root);
    this.child = null;
    this.queue = [];
    this.busy = null;
    this.buffer = "";
    this.seq = 0;
    this.timer = null;
  }

  start() {
    if (this.child) {
      return;
    }
    this.child = spawn(this.target.exe, this.target.args, {
      cwd: this.target.cwd,
      stdio: ["pipe", "pipe", "pipe"],
    });
    this.child.stdout.on("data", (chunk) => this._onData(chunk));
    this.child.stderr.on("data", () => {});
    this.child.on("error", () => this._down());
    this.child.on("exit", () => this._down());
  }

  _down() {
    clearTimeout(this.timer);
    this.timer = null;
    this.buffer = "";
    this.child = null;
    const busy = this.busy;
    this.busy = null;
    if (busy) {
      busy({ items: [], error: "worker exited" });
    }
    this._drain();
  }

  _onData(chunk) {
    this.buffer += chunk;
    let nl;
    while ((nl = this.buffer.indexOf("\n")) >= 0) {
      const raw = this.buffer.slice(0, nl);
      this.buffer = this.buffer.slice(nl + 1);
      if (!raw.trim()) {
        continue;
      }
      let result;
      try {
        result = JSON.parse(raw);
      } catch (err) {
        result = { items: [], error: "bad response" };
      }
      clearTimeout(this.timer);
      this.timer = null;
      const busy = this.busy;
      this.busy = null;
      if (busy) {
        busy(result);
      }
      this._drain();
    }
  }

  _drain() {
    if (this.busy || this.queue.length === 0) {
      return;
    }
    const { payload, resolve } = this.queue.shift();
    this.busy = resolve;
    try {
      this.start();
      const id = ++this.seq;
      this.child.stdin.write(JSON.stringify(Object.assign({ id }, payload)) + "\n");
      this.timer = setTimeout(() => {
        try {
          this.child && this.child.kill();
        } catch (err) {}
        this._down();
      }, 4000);
    } catch (err) {
      this.busy = null;
      resolve({ items: [], error: String(err) });
      this._drain();
    }
  }

  query(payload) {
    return new Promise((resolve) => {
      this.queue.push({ payload, resolve });
      this._drain();
    });
  }

  dispose() {
    clearTimeout(this.timer);
    this.timer = null;
    if (this.child) {
      try {
        this.child.kill();
      } catch (err) {}
    }
    this.child = null;
  }
}

let worker = null;

function ensureWorker() {
  if (!worker) {
    const root = vscode.workspace.workspaceFolders
      ? vscode.workspace.workspaceFolders[0].uri.fsPath
      : null;
    if (!root) {
      return null;
    }
    worker = new DictionaryWorker(root);
    worker.start();
  }
  return worker;
}

async function provideCompletionItems(document, position) {
  const active = ensureWorker();
  if (!active) {
    return [];
  }
  const result = await active.query({
    buffer: document.getText(),
    line: position.line,
    column: position.character,
  });
  return (result.items || []).map((item) => {
    const completion = new vscode.CompletionItem(
      item.label,
      KIND_OF[item.type] || vscode.CompletionItemKind.Value
    );
    if (item.snippet) {
      completion.insertText = new vscode.SnippetString(item.snippet);
    } else if (item.value_shape === "text") {
      completion.insertText = new vscode.SnippetString(
        item.label + ' "${1}"'
      );
    } else {
      completion.insertText = item.insert;
    }
    if (item.detail) {
      completion.detail = item.detail;
    }
    return completion;
  });
}

// The dictionary's own words for the kind or property under the cursor,
// plus what could sensibly follow it. Advisory throughout: the dictionary
// advises and never validates, so hovering never reports a problem.
async function provideHover(document, position) {
  const active = ensureWorker();
  if (!active) {
    return null;
  }
  const result = await active.query({
    hover: true,
    buffer: document.getText(),
    line: position.line,
    column: position.character,
  });
  if (!result || !result.label) {
    return null;
  }
  const md = new vscode.MarkdownString();
  md.appendMarkdown(`**${result.label}**`);
  if (result.meaning) {
    md.appendMarkdown("\n\n");
    md.appendText(result.meaning);
  }
  const items = result.items || [];
  const shown = items.slice(0, HOVER_ITEM_LIMIT);
  if (shown.length) {
    md.appendMarkdown("\n\n");
    shown.forEach((item, index) => {
      if (index) {
        md.appendMarkdown("\n");
      }
      md.appendMarkdown(`- \`${item.label}\``);
      if (item.detail) {
        md.appendMarkdown(" — ");
        md.appendText(item.detail);
      }
    });
    if (items.length > shown.length) {
      md.appendMarkdown(
        `\n\n… and ${items.length - shown.length} more`
      );
    }
  }
  return new vscode.Hover(md);
}

// The canonical text of a document, or null when the worker could not
// answer. Formatting is a whole-document replacement, so the caller must
// never guess at a partial answer: a missing `text` is not "no changes",
// it is "no answer", and the two are kept apart here.
async function canonicalText(document) {
  const active = ensureWorker();
  if (!active) {
    return null;
  }
  const result = await active.query({ format: true, buffer: document.getText() });
  if (!result || typeof result.text !== "string") {
    return null;
  }
  return result.text;
}

// The worker returns the buffer unchanged whenever the formatter has
// nothing to say — an empty file, a comment, a buffer that does not
// parse — so an equal answer is the common case on save and is worth the
// early exit: it leaves the undo stack alone.
async function provideDocumentFormattingEdits(document) {
  const text = await canonicalText(document);
  if (text === null || text === document.getText()) {
    return [];
  }
  const lastLine = Math.max(document.lineCount - 1, 0);
  return [
    vscode.TextEdit.replace(
      new vscode.Range(
        new vscode.Position(0, 0),
        new vscode.Position(lastLine, document.lineAt(lastLine).text.length)
      ),
      text
    ),
  ];
}

// The `ine.format` command formats the active document by asking the
// editor to run its own format action, so the command, format-on-save
// and the Shift+Alt+F keybinding all reach the same provider and there is
// one formatting path rather than three. A document in another language
// is left to whatever formatter it has of its own.
async function formatActiveDocument() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "ine") {
    return;
  }
  await vscode.commands.executeCommand("editor.action.formatDocument");
}

// Parse errors are errors; everything semantic is a warning. Semantic and
// dictionary findings are never red-underlined — they are advisory, and a
// red underline would read as a rule the language does not have.
function toDiagnostic(document, entry, severity) {
  const lastLine = Math.max(document.lineCount - 1, 0);
  const line = Math.min(Math.max(entry.line || 0, 0), lastLine);
  const textLine = document.lineAt(line);
  let range = textLine.range;
  if (typeof entry.column === "number") {
    const start = Math.min(Math.max(entry.column, 0), textLine.text.length);
    const end = Math.min(start + 1, textLine.text.length);
    range = new vscode.Range(
      new vscode.Position(line, start),
      new vscode.Position(line, end)
    );
  }
  return new vscode.Diagnostic(range, entry.message, severity);
}

function refreshDiagnostics(document) {
  if (document.languageId !== "ine") {
    return;
  }
  const active = ensureWorker();
  if (!active) {
    return;
  }
  const pending = diagnosticTimers.get(document.uri.toString());
  if (pending) {
    clearTimeout(pending);
  }
  diagnosticTimers.set(
    document.uri.toString(),
    setTimeout(() => {
      diagnosticTimers.delete(document.uri.toString());
      active.query({ validate: true, buffer: document.getText() }).then((result) => {
        if (document.isClosed) {
          return;
        }
        const found = [];
        for (const entry of result.diagnostics || []) {
          found.push(
            toDiagnostic(document, entry, vscode.DiagnosticSeverity.Error)
          );
        }
        for (const entry of result.advisory || []) {
          found.push(
            toDiagnostic(document, entry, vscode.DiagnosticSeverity.Warning)
          );
        }
        diagnostics.set(document.uri, found);
      });
    }, DIAGNOSTIC_DELAY_MS)
  );
}

function clearDiagnostics(document) {
  const pending = diagnosticTimers.get(document.uri.toString());
  if (pending) {
    clearTimeout(pending);
    diagnosticTimers.delete(document.uri.toString());
  }
  diagnostics.delete(document.uri);
}

function activate(context) {
  ensureWorker();
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      { scheme: "file", language: "ine" },
      { provideCompletionItems },
      ...TRIGGER_CHARS
    )
  );
  context.subscriptions.push(
    vscode.languages.registerHoverProvider(
      { scheme: "file", language: "ine" },
      { provideHover }
    )
  );
  context.subscriptions.push(
    vscode.languages.registerDocumentFormattingEditProvider(
      { scheme: "file", language: "ine" },
      { provideDocumentFormattingEdits }
    )
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("ine.format", formatActiveDocument)
  );
  context.subscriptions.push(diagnostics);
  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument((document) =>
      refreshDiagnostics(document)
    ),
    vscode.workspace.onDidChangeTextDocument((event) =>
      refreshDiagnostics(event.document)
    ),
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor) {
        refreshDiagnostics(editor.document);
      }
    }),
    vscode.workspace.onDidCloseTextDocument((document) =>
      clearDiagnostics(document)
    )
  );
  vscode.workspace.textDocuments.forEach((document) =>
    refreshDiagnostics(document)
  );
  context.subscriptions.push({
    dispose() {
      if (worker) {
        worker.dispose();
        worker = null;
      }
    },
  });
}

module.exports = { activate };