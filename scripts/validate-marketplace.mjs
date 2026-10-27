#!/usr/bin/env node
// Validates the Devin-marketplace shape of this repo. Adapted from
// CognitionAI/team-marketplace-template (scripts/validate-template.mjs).
// Run: node scripts/validate-marketplace.mjs
//
// Checks, per plugin directory:
//   - .devin-plugin/plugin.json parses; name is kebab-case; version is semver
//   - entry plugins: manifest name matches the directory name
//   - skill sources (manifest "skills" path, default "skills/"): every
//     subdir has SKILL.md with front-matter name/description, name == dirname
//   - same-repo git-subdir refs resolve to a real sibling plugin manifest

import { readdirSync, readFileSync, existsSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

// The marketplace meta-plugin plus every catalog entry (skills/_template is a
// template, not a catalog entry, so it is not listed).
const PLUGIN_DIRS = [
  { dir: "marketplace", meta: true },
  { dir: "skills/auto-commit" },
  { dir: "skills/commit-review" },
  { dir: "skills/email-notify" },
  { dir: "skills/gerrit-review-code" },
  { dir: "skills/grill-pack" },
  { dir: "skills/jira" },
  { dir: "skills/jira-worklog" },
  { dir: "mcp/codegraph" },
  { dir: "mcp/gitnexus" },
  { dir: "tools/jira-devin-bot" },
];

const errors = [];
const kebab = /^[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9]+)*$/;

function fail(msg) {
  errors.push(msg);
}

function parseJson(path, label) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (e) {
    fail(`${label}: invalid JSON (${e.message})`);
    return null;
  }
}

function frontmatter(path) {
  const text = readFileSync(path, "utf8");
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) return null;
  const fields = {};
  for (const line of m[1].split(/\r?\n/)) {
    const idx = line.indexOf(":");
    if (idx > 0) fields[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  }
  return fields;
}

// Skill sources: the manifest "skills" field (string or array) redirects where
// skills load from; default is "skills".
function skillPaths(dir, manifest, label) {
  let field = manifest.skills;
  if (field === undefined) return ["skills"];
  if (typeof field === "string") return [field];
  if (Array.isArray(field)) return field.every((p) => typeof p === "string") ? field : [];
  fail(`${label}: "skills" must be a string or an array of strings`);
  return [];
}

function checkSkillLike(dir, kind) {
  if (!existsSync(dir)) return;
  for (const entry of readdirSync(dir)) {
    if (!statSync(join(dir, entry)).isDirectory()) continue;
    const md = join(dir, entry, `${kind === "skill" ? "SKILL" : "AGENT"}.md`);
    const label = md.slice(root.length + 1);
    if (!existsSync(md)) {
      fail(`${label}: missing ${kind === "skill" ? "SKILL" : "AGENT"}.md in ${entry}/`);
      continue;
    }
    const fm = frontmatter(md);
    if (!fm) fail(`${label}: missing YAML frontmatter`);
    else {
      if (!fm.name) fail(`${label}: frontmatter missing "name"`);
      if (!fm.description) fail(`${label}: frontmatter missing "description"`);
      if (fm.name && fm.name !== entry)
        fail(`${label}: frontmatter name "${fm.name}" should match directory "${entry}"`);
    }
  }
}

const names = new Set();
for (const { dir: rel, meta } of PLUGIN_DIRS) {
  const dir = join(root, rel);
  const manifestPath = join(dir, ".devin-plugin", "plugin.json");
  if (!existsSync(manifestPath)) {
    fail(`${rel}: missing .devin-plugin/plugin.json`);
    continue;
  }
  const manifest = parseJson(manifestPath, `${rel}/.devin-plugin/plugin.json`);
  if (!manifest) continue;

  if (!manifest.name) fail(`${rel}: manifest missing "name"`);
  else {
    if (!kebab.test(manifest.name))
      fail(`${rel}: name "${manifest.name}" must be lowercase kebab-case`);
    if (names.has(manifest.name)) fail(`${rel}: duplicate plugin name "${manifest.name}"`);
    names.add(manifest.name);
    // entry dirs are named after the entry; the marketplace meta dir is not
    if (!meta && manifest.name !== rel.split("/").pop())
      fail(`${rel}: manifest name "${manifest.name}" should match directory "${rel.split("/").pop()}"`);
  }
  if (manifest.version && !/^\d+\.\d+\.\d+([-+].*)?$/.test(manifest.version))
    fail(`${rel}: version "${manifest.version}" is not semver`);
  for (const list of ["requiredPlugins", "optionalPlugins", "forbiddenPlugins"]) {
    if (manifest[list] !== undefined && !Array.isArray(manifest[list]))
      fail(`${rel}: "${list}" must be an array`);
  }
  // Same-repo git-subdir references must point at real sibling plugins.
  for (const list of ["requiredPlugins", "optionalPlugins"]) {
    for (const ref of Array.isArray(manifest[list]) ? manifest[list] : []) {
      if (
        typeof ref === "object" &&
        ref !== null &&
        ref.source === "git-subdir" &&
        typeof ref.url === "string" &&
        /\/SC-ANSC-MARKETPLACE(\.git)?$/.test(ref.url) &&
        typeof ref.path === "string"
      ) {
        const target = join(root, ref.path, ".devin-plugin", "plugin.json");
        if (!existsSync(target))
          fail(`${rel}: ${list} entry "${ref.path}" does not resolve to a plugin in this repo`);
      }
    }
  }

  for (const skillsRel of skillPaths(dir, manifest, rel)) {
    checkSkillLike(join(dir, skillsRel), "skill");
  }
  checkSkillLike(join(dir, "agents"), "agent");

  for (const file of ["hooks.json", "mcp_config.json"]) {
    const p = join(dir, file);
    if (existsSync(p)) parseJson(p, `${rel}/${file}`);
  }
}

if (errors.length) {
  console.error(`Marketplace validation failed with ${errors.length} error(s):`);
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}
console.log(`Marketplace validation passed (${PLUGIN_DIRS.length} plugins).`);
