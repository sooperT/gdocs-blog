// Strength labels (trust contract 1: Led / Contributed) per TomBot section.
// One shared table, lib/strength.json, also read by generate_agent_page.py,
// which fails the build if a label's justifying phrase is no longer verbatim
// in its section. Unlabelled sections return null: nothing is inferred.
// Import attribute: Node (20.10+) reads the JSON at run time, esbuild inlines
// it at bundle time (verified locally with `esbuild --bundle`, 2026-10-12).
import STRENGTH from './strength.json' with { type: 'json' };

export function strengthFor(sectionId) {
  const entry = Object.hasOwn(STRENGTH, String(sectionId)) ? STRENGTH[sectionId] : null;
  return entry ? entry.strength : null;
}
