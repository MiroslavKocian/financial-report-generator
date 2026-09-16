# Coding Principles


## Design (OOP)

**Single responsibility** — A class or function should do one thing only.

**Open / closed** — Open for extension, closed for modification.

**Liskov substitution** — Subtypes must be replaceable for their base types.

**Interface segregation** — Prefer small, focused interfaces over fat ones.

**Dependency inversion** — Depend on abstractions, not concretions.

**Composition over inheritance** — Favor assembling small behaviors over deep class hierarchies.


## Universal

**DRY** — Every piece of knowledge should have a single source of truth.

**KISS** — Simplicity is a feature; avoid unnecessary complexity.

**YAGNI** — Don't build for hypothetical future needs.

**Separation of concerns** — Keep distinct responsibilities in distinct modules.

**Principle of least surprise** — Code should behave the way a reader would expect.

**Law of Demeter** — A module should only talk to its immediate dependencies.


## Code Quality

**Fail fast** — Surface errors early and loudly rather than letting them propagate silently.

**Make it work → right → fast** — Correctness before clarity, clarity before optimization.

**Boy scout rule** — Always leave code cleaner than you found it — within scope.

**Error handling is not optional** — Every external call, parse, or IO operation must handle failure.

**No placeholder code** — Never deliver // TODO: implement this — implement it or say you can't.

**Explicit imports and dependencies** — Never assume something is available without showing it.


## Architecture

**High cohesion, low coupling** — Things that belong together stay together; modules stay independent.

**Design for testability** — If something is hard to test, it's probably poorly designed.

**No premature optimization** — Profile before you optimize (Knuth).

**Version everything** — Code, config, infrastructure, data schemas.


## Mindset

**Code is read more than written** — Optimize for the reader, not the writer.

**Explicit over implicit** — Clarity beats cleverness.

**Embrace immutability** — Prefer data that doesn't change; it's easier to reason about.

**Done means working, not elegant** — A task is done when the request is satisfied and nothing previously working is now broken.


## Scope Control

**Strict scope** — Do not add, remove, or refactor anything outside the explicit request.

**Flag, don't fix** — If something broken is spotted nearby, note it — don't silently fix it.

**Smallest viable change** — Prefer the minimal change that solves the problem.

**One concern per response** — Don't bundle refactors with feature additions.

**Preserve existing style** — Match conventions already in the file; don't impose your own.

**Cascade? Ask first** — If a change would cascade widely, stop and ask rather than cascade.


## Communication

**Clarify before assuming** — If intent is ambiguous, ask rather than guess and proceed.

**Explain the why** — When suggesting something non-obvious, say why.

**Surface tradeoffs** — Name what is being traded away, not just what was chosen.

## Project Specific Requirements (Financial Report Generator)

- **No Streamlit** — Use standard web technologies (HTML/FastAPI).
- **Free Tools Only** — No paid APIs or licensed software.
- **Educational Goal** — Prioritize learning Python, SQL, REST APIs, FastAPI, Docker.
- **Step-by-Step** — Go slowly, one function at a time.
- **Documentation** — Comment every line of code for clarity.
- **SQL Mastery** — Write raw SQL queries manually (no ORMs like SQLAlchemy for inserts).
