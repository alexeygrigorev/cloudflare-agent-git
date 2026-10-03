# For tomorrow morning: how to write the daily report

User instruction, 3 October 2026 evening (recorded verbatim in experiment/USER-INSTRUCTIONS.md):

- Claude Opus writes only the morning report. During the rest of the day, the work is carried by the other agents.
- The report must be illustrated, not dry text:
  - at least one generated illustration (image generation) that shows the day's idea in a picture;
  - one to three diagrams that explain how things work (made with the diagram-creator skill), e.g. "several agents, each in its own copy, a referee that tries their changes together and warns early".
- Plain, normal language for an outside reader:
  - no jargon (explain terms like "fork", "merge", "conflict" in everyday words, or avoid them);
  - nothing that only makes sense inside our internal reports;
  - no codes: no commit hashes, session IDs, task IDs, message IDs, review numbers.
- Describe evidence in words ("the agents' changes were tried together and the clash was caught before anyone merged") instead of citing identifiers.

Material available for the 4 October report (describe it, don't cite IDs): the first full run on this computer worked end to end; the first real run on Cloudflare's Git storage worked (creating a repository, copying it per agent, pushing and reading back); the Rust measurement (sharing build output cut disk use about three times and memory about two times at small scale, but was not faster); the landing page now shows the story above the fold; the agents' own resource troubles during the day (disk filling up from Rust builds, a tool that ran every command twice, agents killing themselves by accident) as honest field notes.
