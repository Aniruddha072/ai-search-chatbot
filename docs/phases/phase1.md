# Phase 1 — Domain Layer

**Commit:** `2cdbb48` (feat(domain): define core domain models and contracts)

## What we built
- `src/domain/entities.py`: immutable (`frozen=True`) dataclasses — `Query`, `SearchResult`, `Source`, `Answer`, `EvaluationResult`.
- `src/domain/interfaces.py`: five `abc.ABC` ports — `SearchProvider`, `LLMProvider`, `Ranker`, `Evaluator`, `Cache` — with no concrete implementations yet.
- Unit tests for both: entity invariants and immutability, and interface enforcement (direct instantiation and incomplete implementations both raise `TypeError`).

## What we learned
- `frozen=True` only blocks *reassigning* a field, not mutating an object a field already points to — a `list` field could still be `.append()`-ed to, silently bypassing entity invariants. `tuple` closes that gap because it has no mutating methods.
- The same immutability requirement is also what makes `Query` hashable: a generated `__hash__` needs every field to be hashable, and `list` isn't.
- `abc.ABC` gives *nominal*, runtime-enforced contracts (`TypeError` at instantiation if any `@abstractmethod` is missing), versus `typing.Protocol`'s structural, type-checker-only contracts — explicit inheritance (`class Foo(SearchProvider):`) was chosen so the dependency is visible directly in the code.

## Key design decisions
- The 1–5 sub-query bound from the original spec is enforced in `Query.__post_init__`, not just in prompt wording — an out-of-range `Query` cannot exist regardless of which future code constructs one.
- `LLMProvider.generate_structured`'s schema type is an unbound `TypeVar`, not bound to `pydantic.BaseModel`, so the domain layer still has zero external dependencies even though the concrete Groq client will use Pydantic schemas.
- `Ranker.rank` is synchronous, not `async` — it's pure in-memory computation, unlike every other port here, which are all I/O-bound.

## Challenges faced
- None blocking.
