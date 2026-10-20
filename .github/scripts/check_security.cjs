const ts = require("typescript");
const fs = require("node:fs");
const path = require("node:path");
const policy = require("../quality/log-policy.json");
const methods = new Set(["log", "debug", "info", "warn", "warning", "error", "trace", "fatal", "exception", "critical"]);

function sensitive(name) {
  if (policy.safe_names.includes(name)) return false;
  const words = name.replace(/([a-z0-9])([A-Z])/g, "$1_$2").toLowerCase();
  const compact = words.replace(/[^a-z0-9]/g, "");
  return policy.sensitive_words.includes(compact) || words.split(/[^a-z0-9]+/).some(word => policy.sensitive_words.includes(word)) ||
    ["apikey", "privatekey", "accesskey"].some(word => compact.includes(word));
}

function redacted(node) {
  return ts.isStringLiteralLike(node) && policy.redacted_values.includes(node.text);
}

function risky(node) {
  if (redacted(node)) return false;
  if (ts.isIdentifier(node) && sensitive(node.text)) return true;
  if (ts.isElementAccessExpression(node) && ts.isStringLiteralLike(node.argumentExpression) && sensitive(node.argumentExpression.text)) return true;
  if (ts.isPropertyAssignment(node)) {
    const key = ts.isComputedPropertyName(node.name) ? node.name.expression : node.name;
    if (redacted(node.initializer)) return false;
    if ((ts.isIdentifier(key) || ts.isStringLiteralLike(key)) && sensitive(key.text)) return true;
  }
  if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === "get") {
    if (node.arguments[0] && ts.isStringLiteralLike(node.arguments[0]) && sensitive(node.arguments[0].text)) return true;
  }
  if (ts.isStringLiteralLike(node) && /\bBearer\s+\S+|\b(?:password|token|api[_-]?key|authorization)\s*[:=]\s*\S+/i.test(node.text)) return true;
  if (ts.isTemplateExpression(node) && /(?:password|token|api[_-]?key|authorization)\s*[:=]\s*$/i.test(node.head.text)) return true;
  let found = false;
  ts.forEachChild(node, child => { if (risky(child)) found = true; });
  return found;
}

function scanSource(source, filename) {
  const tree = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true);
  const findings = [];
  const loggers = new Set(["console", "logger", "log", "logging"]);
  const direct = new Set();
  function collect(node) {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && ts.isCallExpression(node.initializer)) {
      if (/(?:getLogger|createLogger|pino|winston|bunyan)$/.test(node.initializer.expression.getText(tree))) loggers.add(node.name.text);
    }
    if (ts.isImportDeclaration(node) && /logger|logging|pino|winston|bunyan/.test(node.moduleSpecifier.text)) {
      const clause = node.importClause;
      if (clause?.name) loggers.add(clause.name.text);
      if (clause?.namedBindings && ts.isNamedImports(clause.namedBindings)) {
        for (const item of clause.namedBindings.elements) if (methods.has((item.propertyName || item.name).text)) direct.add(item.name.text);
      }
    }
    ts.forEachChild(node, collect);
  }
  collect(tree);
  for (const diagnostic of tree.parseDiagnostics) {
    const line = tree.getLineAndCharacterOfPosition(diagnostic.start || 0).line + 1;
    findings.push(filename + ":" + line + ": JavaScript/TypeScript parse error");
  }
  function visit(node) {
    if (ts.isCallExpression(node)) {
      const callee = node.expression;
      let sink = ts.isIdentifier(callee) && direct.has(callee.text);
      if (ts.isPropertyAccessExpression(callee) && methods.has(callee.name.text)) {
        const receiver = callee.expression.getText(tree).split(".");
        sink = receiver.some(name => loggers.has(name) || /logger$/i.test(name));
      }
      if (sink && node.arguments.some(risky)) {
        findings.push(filename + ":" + (tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1) + ": sensitive value passed directly to a logging call");
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  return findings;
}

module.exports = { scanSource };
if (require.main === module) {
  const files = JSON.parse(fs.readFileSync(0, "utf8"));
  const findings = files.flatMap(file => scanSource(fs.readFileSync(path.resolve(file), "utf8"), file));
  for (const finding of findings) console.error(finding);
  process.exitCode = findings.length ? 1 : 0;
}
