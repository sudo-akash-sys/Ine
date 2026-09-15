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
    if (item.value_shape === "text") {
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

function activate(context) {
  ensureWorker();
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      { scheme: "file", language: "ine" },
      { provideCompletionItems },
      ...TRIGGER_CHARS
    )
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