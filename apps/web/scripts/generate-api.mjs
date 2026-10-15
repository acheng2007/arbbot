// Generates apps/web/src/lib/api/schema.ts from the committed docs/openapi.json.
// Run `npm run generate:api`; `npm run generate:api -- --check` fails on drift.
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { format, resolveConfig } from "prettier";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const documentPath = resolve(webRoot, "../../docs/openapi.json");
const outputPath = resolve(webRoot, "src/lib/api/schema.ts");

// Every monetary and quantity field in the backend schema carries this pattern.
// They are emitted as DecimalString so exact values are never parsed into a number.
const DECIMAL_PATTERN = "^(?!^[-+.]*$)[+-]?0*\\d*\\.?\\d*$";

function fail(message) {
  throw new Error(`generate-api: ${message}`);
}

function refName(ref) {
  const prefix = "#/components/schemas/";
  if (!ref.startsWith(prefix)) fail(`unsupported $ref ${ref}`);
  return modelName(ref.slice(prefix.length));
}

function modelName(name) {
  const symbol = name.replace(/-Output$/, "").replace(/-Input$/, "Input");
  if (!/^[A-Za-z_$][\w$]*$/.test(symbol))
    fail(`unsupported model name ${name}`);
  return symbol;
}

function quote(value) {
  return JSON.stringify(value);
}

function typeOf(schema, path) {
  if (schema === undefined) fail(`missing schema at ${path}`);
  if (schema.$ref) return refName(schema.$ref);
  if (schema.const !== undefined) return quote(schema.const);
  if (schema.anyOf || schema.oneOf)
    return (schema.anyOf ?? schema.oneOf)
      .map((option, index) => typeOf(option, `${path}.anyOf[${index}]`))
      .join(" | ");
  if (schema.enum) return schema.enum.map(quote).join(" | ");

  switch (schema.type) {
    case "string":
      if (schema.pattern === DECIMAL_PATTERN) return "DecimalString";
      // OpenAPI date-time values stay as ISO-8601 strings; parsing is the caller's choice.
      return "string";
    case "integer":
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "null":
      return "null";
    case "array": {
      if (schema.prefixItems) {
        const members = schema.prefixItems.map((item, index) =>
          typeOf(item, `${path}.prefixItems[${index}]`),
        );
        if (
          schema.minItems !== members.length ||
          schema.maxItems !== members.length
        )
          fail(`tuple at ${path} must pin minItems and maxItems`);
        return `[${members.join(", ")}]`;
      }
      return `Array<${typeOf(schema.items, `${path}.items`)}>`;
    }
    case "object": {
      if (schema.properties) return objectType(schema, path);
      const value =
        schema.additionalProperties === undefined ||
        schema.additionalProperties === true
          ? "unknown"
          : typeOf(schema.additionalProperties, `${path}.additionalProperties`);
      const keys = schema.propertyNames?.enum
        ? schema.propertyNames.enum.map(quote).join(" | ")
        : "string";
      return `Partial<Record<${keys}, ${value}>>`;
    }
    case undefined: {
      // A schema carrying only annotations accepts any JSON value.
      const annotations = new Set([
        "title",
        "description",
        "default",
        "examples",
      ]);
      if (Object.keys(schema).every((key) => annotations.has(key)))
        return "unknown";
      fail(`untyped schema at ${path}: ${JSON.stringify(schema)}`);
      break;
    }
    default:
      fail(`unsupported type ${schema.type} at ${path}`);
  }
}

function objectType(schema, path) {
  const required = new Set(schema.required ?? []);
  const lines = Object.entries(schema.properties).map(([name, property]) => {
    const optional = required.has(name) ? "" : "?";
    return `  ${JSON.stringify(name)}${optional}: ${typeOf(property, `${path}.${name}`)};`;
  });
  return `{\n${lines.join("\n")}\n}`;
}

// FastAPI builds operationIds as `<handler name><sanitized path>_<method>`.
// Stripping the generated suffix recovers the stable handler name.
function operationKey(operationId, route, method) {
  const suffix = `${route.replace(/\W/g, "_")}_${method}`;
  if (!operationId?.endsWith(suffix))
    fail(
      `operationId ${operationId} does not match the expected FastAPI form for ${route}`,
    );
  const name = operationId.slice(0, -suffix.length);
  if (!name) fail(`empty handler name derived from ${operationId}`);
  return name.replace(/_(\w)/g, (_, character) => character.toUpperCase());
}

function operationsFor(document) {
  const entries = [];
  for (const [route, methods] of Object.entries(document.paths)) {
    for (const [method, operation] of Object.entries(methods)) {
      if (!["get", "post"].includes(method))
        fail(`unsupported method ${method} for ${route}`);
      const parameters = operation.parameters ?? [];
      const query = parameters.filter((p) => p.in === "query");
      const params = parameters.filter((p) => p.in === "path");
      for (const parameter of parameters)
        if (!["query", "path"].includes(parameter.in))
          fail(`unsupported parameter location ${parameter.in} in ${route}`);

      const success = operation.responses["200"] ?? operation.responses["201"];
      const body = success?.content?.["application/json"]?.schema;
      const request =
        operation.requestBody?.content?.["application/json"]?.schema;
      if (operation.requestBody && !request)
        fail(`unsupported request body for ${route}`);
      const key = operationKey(operation.operationId, route, method);
      if (entries.some((entry) => entry.key === key))
        fail(`duplicate operation key ${key}`);
      entries.push({
        route,
        key,
        method: method.toUpperCase(),
        body: request ? typeOf(request, `${route}.body`) : "never",
        params,
        query,
        response: body ? typeOf(body, route) : "unknown",
      });
    }
  }
  return entries;
}

function memberList(parameters, route) {
  if (parameters.length === 0) return "Record<string, never>";
  const lines = parameters.map((parameter) => {
    const optional = parameter.required ? "" : "?";
    return `    ${JSON.stringify(parameter.name)}${optional}: ${typeOf(parameter.schema, `${route}.${parameter.name}`)};`;
  });
  return `{\n${lines.join("\n")}\n  }`;
}

function render(document) {
  const schemas = document.components?.schemas ?? {};
  const operations = operationsFor(document);

  const header = [
    "// Generated by scripts/generate-api.mjs from docs/openapi.json. Do not edit by hand.",
    `// Source document: ${document.info?.title ?? "unknown"} ${document.info?.version ?? ""}`.trim(),
    "",
    "/** Exact decimal transported as a string; never convert this to a number. */",
    "export type DecimalString = string;",
    "",
  ];

  const models = Object.entries(schemas).map(
    ([name, schema]) =>
      `export type ${modelName(name)} = ${typeOf(schema, name)};\n`,
  );
  if (
    new Set(Object.keys(schemas).map(modelName)).size !==
    Object.keys(schemas).length
  )
    fail("model names collide after normalization");

  const routes = operations.map(
    (operation) =>
      `  ${JSON.stringify(operation.key)}: {\n` +
      `    route: ${JSON.stringify(operation.route)};\n` +
      `    method: ${JSON.stringify(operation.method)};\n` +
      `    body: ${operation.body};\n` +
      `    params: ${memberList(operation.params, operation.route)};\n` +
      `    query: ${memberList(operation.query, operation.route)};\n` +
      `    response: ${operation.response};\n` +
      `  };`,
  );

  const table = operations.map(
    (operation) =>
      `  ${JSON.stringify(operation.key)}: {\n` +
      `    route: ${JSON.stringify(operation.route)},\n` +
      `    method: ${JSON.stringify(operation.method)},\n` +
      `    params: [${operation.params.map((p) => JSON.stringify(p.name)).join(", ")}],\n` +
      `    query: [${operation.query.map((p) => JSON.stringify(p.name)).join(", ")}],\n` +
      `  },`,
  );

  return (
    header.join("\n") +
    models.join("\n") +
    "\n/** Every backend operation keyed by its OpenAPI operationId. */\n" +
    `export interface ApiOperations {\n${routes.join("\n")}\n}\n\n` +
    "export type OperationId = keyof ApiOperations;\n\n" +
    'export type ReadOperationId = { [K in OperationId]: ApiOperations[K]["method"] extends "GET" ? K : never }[OperationId];\n\n' +
    "/** Route template and accepted parameter names for each operation. */\n" +
    "export const API_OPERATIONS = {\n" +
    `${table.join("\n")}\n` +
    "} as const satisfies Record<\n" +
    "  OperationId,\n" +
    '  { route: string; method: "GET" | "POST"; params: readonly string[]; query: readonly string[] }\n' +
    ">;\n"
  );
}

const document = JSON.parse(readFileSync(documentPath, "utf8"));
// Formatting through Prettier keeps generated output stable for the drift check.
const generated = await format(render(document), {
  ...(await resolveConfig(outputPath)),
  parser: "typescript",
});
const check = process.argv.includes("--check");

if (check) {
  let current = "";
  try {
    current = readFileSync(outputPath, "utf8");
  } catch {
    current = "";
  }
  if (current !== generated) {
    const digest = (value) =>
      createHash("sha256").update(value).digest("hex").slice(0, 12);
    console.error(
      `Generated API client is out of date (committed ${digest(current)}, expected ${digest(generated)}).\n` +
        "Run `npm run generate:api` in apps/web and commit the result.",
    );
    process.exit(1);
  }
  console.log("Generated API client matches docs/openapi.json.");
} else {
  writeFileSync(outputPath, generated);
  console.log(`Wrote ${outputPath}`);
}
