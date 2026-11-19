---
name: acme-release-notes
description: ACME house style for RELEASE_NOTES.md (title line, section names and order, item format). Use whenever writing ACME release notes.
---
# ACME release-notes house style

File: `RELEASE_NOTES.md`

1. First line exactly: `# <Product> <version> — <YYYY-MM-DD>` (an em dash `—` with single spaces around it).
2. Then exactly these sections, in this order, each as a level-2 heading:
   - `## Highlights` — new features (`feature` changes)
   - `## Fixes` — bug fixes (`fix` changes), sorted by ticket number ascending
   - `## Breaking changes` — `breaking` changes; always present, write `None.` if there are none
3. One bullet (`- `) per change, written for end users (what changed for *them*), one line each.
4. End every bullet with the ticket reference in the form `(ACME-<number>)`. Never `#123` or bare numbers.
5. Breaking changes must say what the user has to do.
6. No emoji, no "Bug fixes"/"Features" headings, no internal jargon.
