---
name: architecture-doc-creator
description: Create architecture documentation following ACDM (Architecture Centric Design Method). Use when users want to create an architecture document for their project, design a system architecture from a concept document, or iteratively build and review architecture documentation with consistency checks.
---

# Architecture Document Creator

Create comprehensive architecture documentation following ACDM (Architecture Centric Design Method) through iterative rounds of analysis, design, and review.

## Overview

This skill takes a concept document (product plan, requirements, etc.) and produces a full set of architecture documents through 5 rounds:

- **Round 0:** Extract architecture significance from the concept document
- **Round 1:** Use case analysis + driver refinement
- **Round 2:** Static view (structure) + architecture patterns
- **Round 3:** Dynamic view (sequence diagrams) + deployment
- **Round 4:** Cross-view mapping + evaluation + ADR + appendix

Each round produces documents, gets user review, runs consistency checks, and incorporates feedback before proceeding.

## Process

### Step 1: Understand the Concept Document

Read the user's concept/plan document thoroughly. Extract:
- Business goals
- Core value proposition
- Target users
- Key features (P0/P1/P2 priority)
- Technical constraints
- KPIs and success metrics

### Step 2: Create the Document Plan

Before writing any architecture content, create a plan document (`architecture_document_plan.md`) that defines:
- The full table of contents
- The iterative round structure (not sequential steps)
- Which sections are created in each round
- Cross-reference consistency check tables

Present the plan for user review before proceeding.

### Step 3: Round 0 — Architecture Significance

Create two files:

**01_introduction.md:**
- Document purpose (ACDM-based)
- Target audience with specific concerns
- Scope (what's in, what's design-consideration-only, what's out)
- Terminology table
- References
- Changes from concept document (track all intentional divergences)

**02_architecture_significance.md:**
- Business goals (BG-N) extracted from concept document
- Architecture drivers:
  - Functional requirements (FR-NN) with BG traceability
  - Quality attribute scenarios (QA-N) in ACDM format (stimulus/response/measure)
  - Constraints (CON-N) with rationale
  - Architectural concerns (AC-N) for non-functional considerations
- Architecture strategies (AS-N) — design philosophies (DDD, Clean Architecture, TDD, etc.)
- Architecture patterns & tactics — concrete patterns per QA

### Step 4: Round 1 — Use Case Analysis

Create **04_dynamic_view.md:**
- Actor definitions with roles
- Use case diagram (UML format: actors left, UCs right, numbered sequentially)
- Use case relationship diagram (include/extend/precedes/depends-on/delegates)
- Full use case scenarios (UC-NN) with:
  - Actor, purpose, preconditions, trigger
  - Related FR/QA cross-references
  - Basic flow, alternative flows, exception flows
  - Postconditions
- Placeholder for sequence diagrams

**Checklist for use case completeness:**
- Cover the full user lifecycle (install → configure → use → update → uninstall)
- Cover the E2E workflow loop from the concept document
- Cover operational concerns (logging, debugging, error handling)
- Cover future/AI integration use cases
- Every FR should be referenced by at least one UC
- Every QA should be referenced by at least one UC

### Step 5: Round 2 — Static View

Create **03_static_view.md** with progressive zoom-in:

1. **System context diagram** — gridflow as a black box, external actors and systems
2. **Conceptual architecture** — map the E2E workflow to major components. Explain the core concepts (e.g., Scenario Pack) BEFORE using them
3. **External system analysis** — analyze each external tool's characteristics (role, computation model, I/O, time semantics). Document design decisions with alternatives comparison
4. **Subsystem decomposition** — map to Clean Architecture layers with ASCII diagram showing spatial grouping of related concepts
5. **Bounded Context Map** — DDD contexts with relationship patterns (Shared Kernel, Supplier-Consumer, Anti-Corruption Layer, Conformist)
6. **Class diagrams** — focus on interface boundaries that embody design decisions, not exhaustive class listings
7. **Extensibility strategy** — how users extend the system at each skill level, with concrete code examples showing WHY it's simple
8. **Deployment diagram** — container structure with design decision rationale
9. **Process view** — bottleneck analysis, thread structure, performance implications

Also create **03b_mechanisms.md** for implementation mechanisms (M-N):
- Logging, error design, OS abstraction, middleware, testing, CI/CD, versioning
- Configuration, serialization, DI, security, i18n, IPC, documentation generation
- Each mechanism: problem → design decision (with alternatives table) → concrete implementation

### Step 6: Round 3 — Sequence Diagrams + Deployment

Add to **04_dynamic_view.md:**
- Sequence diagram for EVERY use case (do not skip any)
- Use static view components as lifelines
- Add analysis/design decision notes after each diagram

Add to **03_static_view.md:**
- Deployment diagram with container separation rationale
- Communication methods table

### Step 7: Round 4 — Cross-View Mapping + Evaluation

Create:
- **05_view_mapping.md** — Component↔UC↔sequence diagram mapping, UC×Component traceability matrix, FR→Component→UC, QA→Tactic→Mechanism→Verification, AS→Static view
- **06_architecture_evaluation.md** — QA achievement assessment, risks, sensitivity points, tradeoffs, open items
- **07_adr.md** — Architecture Decision Records with context/candidates/decision/rationale
- **08_appendix.md** — Concept doc mapping table, QA summary, terminology, references
- **README.md** — Document structure with suggested reading order

## Critical Rules

### Consistency Checks

After EVERY round and EVERY significant change:

1. Run a consistency check agent across ALL documents
2. Check: terminology, ID references, strategy consistency, UC↔FR/QA completeness, concept doc alignment, internal logic, plan TOC vs actual, numbering
3. Fix all MEDIUM+ issues
4. Re-run until MEDIUM+ = 0
5. Only then present results to user

### Self-Review

Before presenting to user, self-review from two perspectives:
- **CEO level:** Are business goals captured? Is the strategy coherent? Are there blind spots?
- **Developer level:** Can I implement from this? Are interfaces clear? Are there hidden dependencies?

### Document Quality Rules

- **Self-contained:** Each document should be understandable without reading external references. If referencing the concept document, include the relevant content inline
- **Explain before use:** Introduce key concepts before using them. Don't assume the reader knows domain-specific terms
- **Design decisions with alternatives:** Every significant design choice should show what alternatives were considered and why this one was chosen
- **Analysis after every diagram:** Each diagram must be followed by explicit analysis explaining what the diagram reveals and what design decisions it embodies
- **No design debt:** Don't write "P0 is simple, we'll fix later." Design it correctly from the start
- **Language-agnostic until decided:** Don't mention specific programming languages in architecture docs until the language choice is made as an ADR
- **Progressive detail:** Each section should zoom in from the previous one. The reader should never feel a conceptual gap between sections

### Iterative Nature

- Architecture documentation is NOT sequential. You will go back and update earlier sections as later analysis reveals issues
- When updating one document, check all others for consistency
- Track all changes from the concept document in section 1.6 (Changes from Plan)
- The concept document itself should be updated when architecture decisions change its premises

## Output Structure

```
docs/architecture/
├── README.md
├── 01_introduction.md
├── 02_architecture_significance.md
├── 03_static_view.md
├── 03b_mechanisms.md
├── 04_dynamic_view.md
├── 05_view_mapping.md
├── 06_architecture_evaluation.md
├── 07_adr.md
└── 08_appendix.md
```
