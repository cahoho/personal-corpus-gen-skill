# Vault Schema and Template Mapping

This reference supplies initial conventions; an existing Vault's `01 System/SCHEMA.md` describes that Vault's actual rules. The skill package and the user's Vault are separate. These templates are instructional scaffolding, not evidence or factual claims about the user. Do not treat their headings, comments or placeholders as real memories, dates, sources, events, quotations or user preferences.

## Authorization and copying

1. Confirm the target Vault, intended files, writable scope and data destinations. Preview the source-to-destination plan and get user authorization before creating directories or copying templates into the Vault.
2. Create only what is needed. Check each destination first. **Never overwrite existing user content with a template**, even when a filename matches; report the collision and preserve the file. For an existing Vault, inspect its actual rules and propose a targeted, reviewable change rather than replacing the schema or core files. Changing an existing meaning, migration, bulk modification or deletion requires the appropriate explicit confirmation and a recovery plan.
3. Copy initial files as UTF-8 Markdown, preserving their contents and relative destinations. The main MOC links to the four core self files; the entry links to privacy rules, main MOC and schema. If a user approves only a subset, ensure links are appropriate to the approved, actually existing files and do not invent links to absent notes. The private MOC and folder are created only if included in the authorized plan.
4. Optional note templates may be installed into `01 System/Templates/` with authorization, or copied directly from the skill package when needed. For an individual note, preview and confirm its actual destination, copy the corresponding template to a new, non-existing filename in the proper folder, and replace the heading and instructional comments with supported content. Do not leave template instructions masquerading as user information. Never copy an instructional example as a personal fact.
5. No operation here authorizes importing conversations, reading the private area, uploading, sharing, deleting or modifying source data. Obtain the necessary separate scope and consent for those actions. Do not create speculative topics, events, projects or empty directory trees merely to satisfy the layout.

## Initial files: exact source-to-target mapping

All source paths below are relative to `personal-corpus/`; target paths are relative to the user's selected Vault root. Copy only the authorized, needed files.

| Template source | Destination in Vault | Purpose |
| --- | --- | --- |
| `assets/templates/00 Start Here.md` | `00 Start Here.md` | Entry, minimal reading order, privacy and time boundaries |
| `assets/templates/01 System/SCHEMA.md` | `01 System/SCHEMA.md` | Actual Vault conventions, subject to user customization |
| `assets/templates/02 Self/Identity.md` | `02 Self/Identity.md` | Supported self-descriptions and values |
| `assets/templates/02 Self/Profile.md` | `02 Self/Profile.md` | Time-sensitive basic information |
| `assets/templates/02 Self/Privacy & Boundaries.md` | `02 Self/Privacy & Boundaries.md` | Rules, not private facts |
| `assets/templates/02 Self/How to Work With Me.md` | `02 Self/How to Work With Me.md` | Contextual collaboration preferences |
| `assets/templates/06 MOCs/MOC - Personal Corpus.md` | `06 MOCs/MOC - Personal Corpus.md` | Ordinary navigation, without private titles or links |
| `assets/templates/07 Privacy/MOC - Private.md` | `07 Privacy/MOC - Private.md` | Private rules and navigation, itself subject to private access restrictions |

## Optional on-demand note templates

Each row can be installed at the specified template path, if authorized. When a real note is needed, copy that template to a new filename at the creation location; `{name}` below is a placeholder to replace with an actual appropriate filename, not an actual fact or literal required title.

| Template source | Optional installed template path | New note creation location |
| --- | --- | --- |
| `assets/templates/01 System/Templates/Topic.md` | `01 System/Templates/Topic.md` | `03 Topics/{name}.md` |
| `assets/templates/01 System/Templates/Event.md` | `01 System/Templates/Event.md` | `04 Events/{name}.md` |
| `assets/templates/01 System/Templates/Project.md` | `01 System/Templates/Project.md` | `05 Projects/{name}.md` |
| `assets/templates/01 System/Templates/Source.md` | `01 System/Templates/Source.md` | `90 Sources/{name}.md` |
| `assets/templates/01 System/Templates/Inbox.md` | `01 System/Templates/Inbox.md` | `00 Inbox/{name}.md` |

`99 Archive/` is optional and means retained history, not deletion. A separate note or directory should be created only when its content warrants it. Sensitive candidates do not go into the ordinary Inbox; after specific user approval, essential private material belongs under `07 Privacy/`, in the minimum necessary form.

## Evidence and dates

Keep a memory's content, relevant conditions, basis, source and useful known time together. `stated` means an explicit user statement; `observed` means an observation supported by multiple behaviors; `inferred` means an inference. Put basis beside each statement when entries differ, not in a misleading file-level field. An AI answer is not by itself proof of a user fact. Unconfirmed non-sensitive inferences, ambiguity and conflicts remain candidates, not confirmed facts. User corrections take priority; preserve relevant changes and uncertainty.

Use an actual source-batch note and a real locator where available; explicitly say when the source or locator is unavailable. Record event time separately from mention time. `created` and `updated` describe the note, `event_date` the event, `valid_as_of` the scope of a particular known fact or entire note only when uniformly applicable, and `last_mentioned` the latest explicit mention in processed records with known dates. Do not use a chat date as an event date or imply complete platform coverage. Omit unknown date fields and preserve partial precision in prose. A `status` needs evidence or confirmation; `aliases` is a YAML list; `sensitivity` is a hint, not access control. Never populate dates, statuses, source links or claims speculatively.

Preserve summaries rather than bulk transcripts. A few necessary short quotations may be retained with real sources and context, subject to the user's privacy rules; never invent a quote or copy a large transcript. Source batch notes should record actual available scope, dates, locators and limitations without automatically copying originals. Minimize third-party information; credentials and keys do not belong in the Vault. Source IDs and hashes can reveal associations and are not anonymization.

There are no reminders, elapsed-time thresholds, scheduled jobs or automatic alerts. Consult or calculate time only when the user asks or the current task requires it. A lack of recent mentions does not establish that a project ended or a preference changed.

## Privacy and compatibility

Routine reading, full-text search, indexing, summaries, exports and model context exclude `07 Privacy/`. Never read, search, expand, embed, quote or send any of its content to a model unless the current request truly requires it and the user explicitly agrees to the specific scope. The private MOC has the same boundary and is read only when needed to establish private rules or navigation. If a tool cannot exclude that folder from an ordinary search, stop using that search method and explain. Ordinary MOCs must not list private titles, links, summaries or facts.

This is a usage rule, not encryption or technical access control. File access, plugins, indexers, synchronization and external models may still expose or upload content; control their access and data destinations separately. Any AI may use the Vault only when actually given access by the user; there is no brand whitelist or guarantee of compliance. Before export, sharing, upload or deletion, confirm destination, scope and risk, and inspect filenames, metadata, links, embeds and attachments as well as text. External copies may be impossible to retract.

Use standard UTF-8 Markdown and valid YAML frontmatter; no plugin or database is required. Stable unique filenames or path-qualified Obsidian wikilinks aid navigation, but wikilinks are not standard Markdown and readers may not follow them. Supply ordinary Markdown and paths when needed for export. Schema or template upgrades must not silently replace a customized Vault: compare changes, obtain approval for any migration, provide recovery and verify the result.
