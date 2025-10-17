# Meta-Process v3: Self-Hydrating Workflow System

**Purpose**: Transform projects into self-hydrating workflow systems with 5-minute agent onboarding

**Version**: 3.0 (Streamlined for universal oodx adoption)
**Updated**: 2025-10-11
**Proven**: RSB, tested across multiple projects

---

## Core Principles

**Self-hydrating system enables**:
- 5-minute productive agent starts
- 30-second urgent context
- Zero manual context reconstruction
- Seamless session handoffs
- Automatic documentation validation

**Meta Process v3 is**:
- **Lightweight**: Core files only (no optional complexity)
- **Universal**: Works for all oodx projects
- **Tested**: Battle-proven in RSB development
- **Adaptive**: System adjusts to project evolution

---

## Required File Structure

### Mandatory Files

**Project Root**:
```
START.txt              # Single entry point (ONLY process doc in root)
LICENSE                # Keep at root (industry standard)
README.md              # Keep at root (industry standard)
```

**docs/procs/** (Process & Status):
```
PROCESS.txt            # Master workflow guide
HANDOFF.md             # Session documentation (MANDATORY at session end)
QUICK_REF.txt          # 30-second context
TASKS.txt              # Active work ONLY (no completed items)
DONE.txt               # Completed archive (current period)
ROADMAP.txt            # Strategic milestones
```

**CRITICAL v3 Requirement**: All docs/procs/ files MUST start with:
```
Last Updated: YYYY-MM-DD
```
This makes document staleness immediately visible. MANDATORY once v3 activated.

**docs/dev/** (Development Guides):
```
CONTRIBUTING.md        # Contributor guide (Oxidex universal)
MODULE_SPEC.md         # Module patterns
CHECKLIST.md           # SDLC checklists
[PROJECT]_ARCH.md      # Architecture (project-specific)
```

### Optional Files

**docs/misc/**: Miscellaneous docs without clear home

**_archive/**: Historical archives (DONE.old.txt, old session files, old sprint data)

**.analysis/**: AI agent analysis outputs (if using agents)

### Deprecated from v2

**SPRINT.txt**: REMOVED in v3 - use TASKS.txt for work tracking, ROADMAP.txt for milestones

**CONTINUE.md**: RENAMED to HANDOFF.md in v3 - emphasizes comprehensive session documentation

**Migration from v2**:
- If SPRINT.txt exists: Extract to TASKS.txt or ROADMAP.txt, then delete
- If CONTINUE.md exists: Rename to HANDOFF.md
- Update all references: CONTINUE.md → HANDOFF.md

---

## Implementation Steps

### Phase 1: Core Structure (30 minutes)

**Create directories**:
```bash
mkdir -p docs/{procs,dev,feats,misc}
mkdir -p _archive
```

**Create START.txt**:
```txt
====
 🚀 [PROJECT] - START HERE
====

📋 Read docs/procs/PROCESS.txt for complete workflow
⚡ Read docs/procs/QUICK_REF.txt for 30-second context

🎯 Quick Start (5 minutes):
1. docs/procs/PROCESS.txt - Master workflow
2. docs/procs/HANDOFF.md - Current session
3. docs/procs/TASKS.txt - Active work (pending only)

📁 All process docs: docs/procs/
🔄 Self-Hydrating System: No manual context reconstruction!
====
```

**Create PROCESS.txt**: Master workflow guide covering:
- Project structure
- Development workflow
- Session patterns
- Tool usage
- Reference links

**Create QUICK_REF.txt**: Ultra-concise context
- Current focus (1-2 lines)
- Project status (3-5 bullets)
- Critical context (blockers, decisions)
- Active tasks (top 3)
- Immediate next steps

**Create HANDOFF.md**: Comprehensive session documentation (MANDATORY)
```markdown
Last Updated: YYYY-MM-DD

# Session Handoff Log

Meta Process: v3

## Session: [YYYY-MM-DD] - [Session Title/Focus]

### Session Summary
[Brief overview of what this session accomplished]

### Key Steps
1. [Major step with rationale]
2. [Major step with rationale]
3. [Major step with rationale]

### Realizations and Learnings
- [Important insights discovered]
- [Pattern improvements identified]
- [Architecture decisions made]

### Experiments and Explorations
- [What was tried and results]
- [Alternative approaches considered]
- [Dead ends encountered]

### Files Modified
- src/module/file.rs - [What changed and why]
- docs/feats/FEATURES_X.md - [Updates made]
- tests/sanity/module.rs - [Tests added]

### Completed Work
- [Task-01]: [Description with file references]
- [Task-02]: [Description with deliverables]

### Next Steps
- [Immediate priority for next session]
- [Pending work to continue]
- [Decisions needed]

### Blockers
- [Issues blocking progress with context]
- [Dependencies waiting on]

### Commits
- abc1234: [Commit message summary]
- def5678: [Commit message summary]

### Session Metrics
- Story Points: X SP completed
- Files Changed: N files
- Tests Added: N tests
- Documentation: X lines added
```

**MANDATORY**: Create/update HANDOFF.md at end of EVERY session with comprehensive context

**Create TASKS.txt**: Active work with proper structure
```txt
## Task Structure Requirements

See PROCESS.txt for complete task requirements and epic patterns.

### Epic Naming Conventions
- DOCS-NN: Documentation work
- BUGS-NN: Bug fixes
- UAT-NN: User acceptance testing
- QOL-NN: Quality of life improvements
- REF-NN: Refactoring
- HUB-NN: Hub integration work
- RSB-NN: RSB-specific work (or PROJECT-NN for other projects)
- M0: Setup/skeleton/sanity/foundational (milestone 0)

### Task Template
**[EPIC-NN]: Task Title** [X SP] ⭐ PRIORITY

**Context**: Why this task exists
**Files**: src/module/file.rs, tests/sanity/module.rs
**Requirements**:
- [ ] Implementation with sufficient detail
- [ ] Unit and integration tests (all green, no fake tests)
- [ ] FEATURES_*.md updated via featpy
- [ ] README updated as needed
- [ ] UAT signoff (shell script for stakeholder demo)

**Story Points**: Complexity estimate
**Success Criteria**: Clear completion conditions
**Deliverable**: What gets produced

### Backlog Graduation
Only backlog items graduated from ROADMAP TODO-NN can be added to TASKS.

### ACTIVE WORK 🔄

PRIORITY 0: [Current focus epic]
BACKLOG: [Graduated from ROADMAP]
DEFERRED: [Low priority]
```

**Create DONE.txt**: Completed archive
- Current sprint/period only
- Archive old work to _archive/DONE.old.txt

**Create ROADMAP.txt**: Strategic milestones and backlog
```txt
## Completed Milestones
- M1: [Milestone] ✅ (Date, SP delivered)

## Current Milestone
- M2: [Active milestone] (SP in progress)

## Future Milestones (Prioritized by Urgency)
- M3: [Next urgent milestone]
- M4: [Future milestone]

## Backlog (TODO-NN)
Items here can be graduated to TASKS.txt when prioritized.

**TODO-01**: [Backlog item title] [X SP]
- Full details, context, requirements
- Story points estimated
- Success criteria defined
```

### Phase 2: Process Integration (15 minutes)

**Establish workflow**:
1. Start session → Read HANDOFF.md
2. Check TASKS.txt for priorities
3. Work on task
4. Archive to DONE.txt when complete
5. Update HANDOFF.md before ending session

**Key discipline**: HANDOFF.md updates are MANDATORY every session

### Phase 3: Validation (15 minutes)

**Test with fresh agent**:
- Can agent find START.txt?
- Does agent follow PROCESS → CONTINUE → TASKS?
- Agent productive within 5 minutes?
- No redundant questions about status?

**Success**: Agent demonstrates understanding without guidance

---

## File Purposes

### START.txt
- **Location**: Project root (only process doc here)
- **Purpose**: Single entry point
- **Content**: Points to PROCESS.txt and QUICK_REF.txt
- **Update**: Rarely (only if core paths change)

### PROCESS.txt
- **Location**: docs/procs/
- **Purpose**: Master workflow guide
- **Content**: How to work in this project
- **Update**: When workflows evolve

### HANDOFF.md
- **Location**: docs/procs/
- **Purpose**: Comprehensive session documentation for project stream continuation
- **Content**:
  - All work done in session (key steps, rationale)
  - Realizations and learnings (insights, decisions)
  - Experiments and explorations (what was tried, results, dead ends)
  - Files modified (with what changed and why)
  - Completed work, next steps, blockers
  - Commits with summaries
  - Session date and metrics
- **Update**: MANDATORY at end of EVERY session
- **Goal**: Enable continuation with sufficient context (no information loss)

### QUICK_REF.txt
- **Location**: docs/procs/
- **Purpose**: 30-second context
- **Content**: Current focus, status, next steps
- **Update**: When project focus shifts

### TASKS.txt (CRITICAL HYGIENE)
- **Location**: docs/procs/
- **Purpose**: Active work tracking with zero-context task breakdown
- **Content**: Epics with story-pointed tasks (PRIORITY 0, BACKLOG, DEFERRED)
- **Structure**: See PROCESS.txt for task template and epic patterns
- **MUST**:
  - Only pending/backlog work - NO completed items
  - Tasks broken down with story points, files, success criteria
  - Sufficient detail for zero-context completion
  - Backlog items ONLY from graduated ROADMAP TODO-NN
- **Update**:
  - Add new tasks as discovered or graduated from ROADMAP
  - Remove IMMEDIATELY when complete (archive to DONE.txt)
  - Keep clean and focused
- **Rule**: Completed work in TASKS.txt is a hygiene violation
- **Epic Patterns**: DOCS-NN, BUGS-NN, UAT-NN, QOL-NN, REF-NN, HUB-NN, PROJECT-NN, M0

### DONE.txt (CRITICAL HYGIENE)
- **Location**: docs/procs/
- **Purpose**: Completed work archive
- **Content**: Current sprint/period achievements ONLY
- **MUST**: Archive when file gets too large (500+ lines)
- **Update**:
  - Archive completed work with commits, deliverables, metrics
  - When large (500+ lines), move to _archive/DONE.old.txt and start fresh
  - Keep current period focused
- **Rule**: DONE.txt should be manageable size (under 500 lines ideal)

### ROADMAP.txt
- **Location**: docs/procs/
- **Purpose**: Strategic milestones and backlog storage
- **Content**:
  - Completed milestones (with dates, SP delivered)
  - Current milestone (active work)
  - Future milestones (prioritized by urgency)
  - Backlog (TODO-NN with full details, story points)
- **Backlog Graduation**: Items move from ROADMAP TODO-NN → TASKS.txt when prioritized
- **Update**: When completing major epics or adding strategic work
- **Note**: Only key milestones (M0, M1, M2, etc.) - not individual tasks

---

## Tools Integration

### testpy Integration
- Access docs: `testpy docs`
- Pulls from brain (canon source)
- Local copies may exist

### featpy Integration
- Syncs features to brain: `featpy sync`
- Makes project features globally accessible
- Auto-updates API documentation

### Process Tools
- blade: Dependency tracking
- semv: Version management
- superclean: Disk cleanup

See docs/dev/CONTRIBUTING.md for complete tool reference

---

## Maintenance

### Every Session (MANDATORY)
- [ ] Update HANDOFF.md with session summary
- [ ] Update "Last Updated: YYYY-MM-DD" timestamp in HANDOFF.md
- [ ] Archive completed work to DONE.txt (with commits, deliverables)
- [ ] Remove completed items from TASKS.txt IMMEDIATELY
- [ ] Verify TASKS.txt contains ONLY pending/backlog work
- [ ] Update "Last Updated" timestamps in any modified proc files

### When Focus Shifts
- [ ] Update QUICK_REF.txt with new focus
- [ ] Update TASKS.txt priorities

### When DONE.txt Grows Large (500+ lines)
- [ ] Move current DONE.txt to _archive/DONE.old.txt
- [ ] Create fresh DONE.txt for new period
- [ ] Keep DONE.txt focused on current sprint/period

### When Milestones Complete
- [ ] Update ROADMAP.txt with completed milestone
- [ ] Archive major completed work to DONE.txt
- [ ] Clean up TASKS.txt

### Regular
- [ ] Validate docs (if validation script exists)
- [ ] Test with fresh agent periodically
- [ ] Review and update PROCESS.txt as workflow evolves

### Migrating from v2
- [ ] Delete SPRINT.txt (deprecated in v3)
- [ ] Extract any useful sprint info to TASKS.txt or ROADMAP.txt
- [ ] Remove sprint references from PROCESS.txt

---

## Success Metrics

**Before Meta Process**:
- 30+ minutes for context reconstruction
- Inconsistent handoffs
- Scattered documentation
- Lost context between sessions

**After Meta Process v3**:
- 5-minute productive starts
- 30-second urgent context
- Perfect session handoffs
- Single source of truth
- Zero context loss

---

## Best Practices

### Do
- ✅ Update HANDOFF.md every session (MANDATORY)
- ✅ Remove completed items from TASKS.txt IMMEDIATELY
- ✅ Archive to DONE.txt when completing work
- ✅ Archive DONE.txt to _archive/ when it exceeds 500 lines
- ✅ Keep QUICK_REF.txt current with project focus
- ✅ Use testpy docs for documentation
- ✅ Keep TASKS.txt clean (pending/backlog only)

### Don't
- ❌ Clutter project root (only START.txt, LICENSE, README.md)
- ❌ Skip HANDOFF.md updates
- ❌ Leave completed work in TASKS.txt (hygiene violation)
- ❌ Let DONE.txt grow unbounded (archive at 500+ lines)
- ❌ Mix process docs with reference docs
- ❌ Create SPRINT.txt (deprecated in v3)

---

## Meta Process Evolution

**v1**: Initial process documentation patterns
**v2**: Self-hydrating with agent analysis, SPRINT.txt for sprint tracking
**v3**: Streamlined universal adoption
- SPRINT.txt removed (TASKS.txt sufficient)
- TASKS/DONE hygiene rules enforced
- Brain integration (testpy/featpy)
- Proven in RSB development

**Next**: v4 will add automation hooks and validation extensions

**v2 → v3 Migration**: Delete SPRINT.txt, enforce TASKS/DONE hygiene

---

## Task Structure Requirements

### Task Breakdown Rules

**All tasks MUST**:
1. Be organized into epics (DOCS-NN, BUGS-NN, etc.)
2. Have story point estimates (complexity)
3. Include sufficient detail for zero-context completion
4. Reference specific files and line numbers
5. Define clear success criteria
6. Be properly sized (if too large, break down further)

### Standard Epic Patterns

- **DOCS-NN**: Documentation work
- **BUGS-NN**: Bug fixes and corrections
- **UAT-NN**: User acceptance testing
- **QOL-NN**: Quality of life improvements
- **REF-NN**: Refactoring and code cleanup
- **HUB-NN**: Hub integration work
- **PROJECT-NN**: Project-specific work (RSB-NN, SKULL-NN, etc.)
- **M0**: Setup/skeleton/sanity/foundational tasks (milestone 0)
- **TODO-NN**: Backlog items in ROADMAP (not in TASKS until graduated)

### Task Completion Definition

**A task is NOT complete until**:
1. ✅ Implementation finished
2. ✅ Unit tests added (all green, no fake tests)
3. ✅ Integration tests added (all green, validated)
4. ✅ FEATURES_*.md updated (via `featpy update <feature>`)
5. ✅ README updated as needed
6. ✅ **UAT signoff obtained** (stakeholder demo via shell script)

**UAT Signoff Requirements**:
- Single shell script stakeholders can run
- No complex cargo commands required
- No setup/harnessing needed by stakeholder
- Can use testpy infrastructure to wrap complexity
- Simple invocation: `./bin/demo-<feature>.sh` or similar
- Demonstrates feature working as required

Example:
```bash
#!/bin/bash
# bin/demo-object-merge.sh - UAT demo for Object::merge() feature
echo "Demonstrating Object<T>::merge() feature..."
cargo run --example object_merge_demo --features object
echo "✓ Feature demonstration complete"
```

### Story Point Guidelines

- **1 SP**: 1-2 hours, single file, clear pattern
- **2 SP**: Half day, 2-3 files, straightforward
- **3 SP**: Full day, multiple files, some complexity
- **5 SP**: 2-3 days, significant work, integration needed
- **8 SP**: Week-long, major feature, break down if possible
- **13+ SP**: TOO LARGE - must break down into smaller tasks

### Backlog Management

**ROADMAP.txt holds backlog as TODO-NN**:
- Full details included (context, requirements, story points)
- Prioritized by urgency
- Graduated to TASKS.txt when ready for active work

**Rule**: TASKS.txt backlog items MUST come from ROADMAP graduation

---

Last Updated: 2025-10-11
Applies To: All Oxidex projects

