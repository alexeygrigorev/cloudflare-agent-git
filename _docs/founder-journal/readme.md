# Founder journal

This folder keeps what the founder said, in the founder's own words.

- [messages/](messages/) holds the words. One file per message.
- [journal.md](journal.md) is a timeline of those files, by date.
- [failures.md](failures.md) says what went wrong and what we changed.

## Rules

- Verbatim. Never paraphrase, shorten or tidy a message.
- Append only. Do not edit or delete a saved message. If a message is later overruled, add the new message; keep the old one.
- One file per message.

## Adding a message

1. Create `messages/YYYYMMDD-NN-short-kebab-subject.txt`, with NN the next number for that day.
2. First line: `Human instruction, D Month YYYY, verbatim:`, then a blank line, then the exact words.
3. Add a row to [journal.md](journal.md) in the same commit.

## What else is in messages/

- `rescued/` holds words found only in documents that were deleted from the tree. Each file says where it came from.
- `human-*.txt` are the earlier saved messages, kept under their original file names so existing references still work.
- `human-coordinator-handoff-and-reports-20261006.md` is a summary, not the founder's words.
- `user-instructions.md` is the early log of instructions, kept whole. In places it holds an agent's interpretation of what the founder meant, not the founder's words. Treat only the verbatim files above as the founder's wording.
