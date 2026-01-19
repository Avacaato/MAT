# PRD: MAT - Local LLM Build Framework

## Introduction

MAT (Multi-Agent Toolkit) is a framework that adapts the BMAD agent-based methodology and Ralph's autonomous build loop to run entirely on local LLMs within a DGX environment. This enables teams to maintain data privacy while leveraging AI-assisted development workflows customized for their codebase.

The framework combines:
- **BMAD's 12+ specialized agents** for planning, architecture, and development
- **50+ guided workflows** across 4 development phases
- **Ralph's autonomous build loop** for story-by-story implementation
- **Scale-adaptive intelligence** (Levels 0-4) for projects of any size

## Goals

- Run the complete BMAD agent workflow on a local LLM via Ollama
- Execute the Ralph build loop autonomously using local inference
- Generate PRDs with discovery interviews and user story creation
- Support OpenAI-compatible API for seamless LLM integration
- Provide CLI interface for the 4-person ML team
- Successfully complete a sample project end-to-end

## User Stories

### US-001: Set up Ollama integration layer
**Description:** As a developer, I need a module that communicates with Ollama's OpenAI-compatible API so that all agents can use the local LLM.

**Acceptance Criteria:**
- [ ] Create `llm/client.py` with OpenAI-compatible client pointing to Ollama
- [ ] Support configurable base URL and model name via environment variables
- [ ] Include retry logic with exponential backoff for failed requests
- [ ] Add streaming response support for long generations
- [ ] Handle connection refused error with clear message "Ollama not running at {url}"
- [ ] Handle model not found error with clear message listing available models
- [ ] Validate response is not empty or malformed before returning
- [ ] Typecheck passes

### US-002: Create base agent class
**Description:** As a developer, I need a base agent class that all specialized agents inherit from so that agent behavior is consistent.

**Acceptance Criteria:**
- [ ] Create `agents/base.py` with BaseAgent class
- [ ] BaseAgent has: name, role, system_prompt, and chat() method
- [ ] chat() method sends messages to LLM client and returns response
- [ ] Support conversation history management
- [ ] Truncate conversation history when approaching context window limit
- [ ] Handle malformed LLM responses gracefully with retry
- [ ] Typecheck passes

### US-003: Implement Product Manager agent
**Description:** As a user, I want a PM agent that conducts discovery interviews and gathers requirements so that projects start with clear goals.

**Acceptance Criteria:**
- [ ] Create `agents/pm.py` with ProductManagerAgent class
- [ ] Agent conducts discovery interview (problem, users, features, success, scope)
- [ ] Agent asks one question at a time and waits for response
- [ ] Agent summarizes findings and confirms understanding
- [ ] Typecheck passes

### US-004: Implement Architect agent
**Description:** As a user, I want an Architect agent that designs technical solutions so that projects have solid foundations.

**Acceptance Criteria:**
- [ ] Create `agents/architect.py` with ArchitectAgent class
- [ ] Agent proposes tech stack based on requirements
- [ ] Agent identifies components, APIs, and data models
- [ ] Agent documents architecture decisions
- [ ] Typecheck passes

### US-005: Implement Developer agent
**Description:** As a user, I want a Developer agent that writes code for user stories so that implementation is automated.

**Acceptance Criteria:**
- [ ] Create `agents/developer.py` with DeveloperAgent class
- [ ] Agent reads user story and acceptance criteria
- [ ] Agent generates code that satisfies criteria
- [ ] Agent can read existing files for context
- [ ] Agent writes files to the project
- [ ] Typecheck passes

### US-006: Implement UX Designer agent
**Description:** As a user, I want a UX agent that designs user interfaces so that the product is usable.

**Acceptance Criteria:**
- [ ] Create `agents/ux.py` with UXDesignerAgent class
- [ ] Agent creates component specifications
- [ ] Agent defines user flows and interactions
- [ ] Agent follows accessibility best practices
- [ ] Typecheck passes

### US-007: Implement Scrum Master agent
**Description:** As a user, I want a Scrum Master agent that manages workflow and progress so that builds stay on track.

**Acceptance Criteria:**
- [ ] Create `agents/scrum_master.py` with ScrumMasterAgent class
- [ ] Agent tracks story completion status
- [ ] Agent identifies blockers and suggests solutions
- [ ] Agent manages the build queue
- [ ] Typecheck passes

### US-008: Implement QA Tester agent
**Description:** As a user, I want a QA agent that verifies implementations so that code quality is maintained.

**Acceptance Criteria:**
- [ ] Create `agents/qa.py` with QATesterAgent class
- [ ] Agent verifies acceptance criteria are met
- [ ] Agent runs type checks and linting
- [ ] Agent reports pass/fail status with details
- [ ] Typecheck passes

### US-009: Create agent orchestrator
**Description:** As a developer, I need an orchestrator that coordinates multiple agents so that they work together on tasks.

**Acceptance Criteria:**
- [ ] Create `orchestrator/coordinator.py` with AgentOrchestrator class
- [ ] Orchestrator routes tasks to appropriate agents
- [ ] Orchestrator passes context between agents
- [ ] Orchestrator manages conversation flow
- [ ] Typecheck passes

### US-010: Implement PRD generation workflow
**Description:** As a user, I want a workflow that generates PRDs from discovery interviews so that projects are well-documented.

**Acceptance Criteria:**
- [ ] Create `workflows/prd_generator.py`
- [ ] Workflow uses PM agent for discovery interview
- [ ] Workflow generates structured PRD markdown
- [ ] Workflow saves PRD to `tasks/prd.md`
- [ ] PRD includes: overview, goals, user stories, requirements, non-goals
- [ ] Typecheck passes

### US-011: Implement story quality checker
**Description:** As a user, I want stories validated before building so that they are properly scoped.

**Acceptance Criteria:**
- [ ] Create `workflows/story_quality.py`
- [ ] Check stories are 1-2 lines max
- [ ] Check stories have specific acceptance criteria
- [ ] Check stories are ordered by dependencies
- [ ] Split large stories automatically
- [ ] Typecheck passes

### US-012: Implement edge case analyzer
**Description:** As a user, I want edge cases identified and added to stories so that implementations are robust.

**Acceptance Criteria:**
- [ ] Create `workflows/edge_cases.py`
- [ ] Analyze PRD for input edge cases (empty, invalid, boundary)
- [ ] Analyze for state edge cases (race conditions, concurrent access)
- [ ] Add edge cases to acceptance criteria
- [ ] Typecheck passes

### US-013: Create prd.json converter
**Description:** As a developer, I need to convert PRD markdown to JSON format so that Ralph can process stories.

**Acceptance Criteria:**
- [ ] Create `workflows/prd_to_json.py`
- [ ] Parse user stories from markdown PRD
- [ ] Generate JSON with project name, branch, and stories array
- [ ] Each story has: id, description, acceptanceCriteria, priority, passes (false)
- [ ] Save to `prd.json` in project root
- [ ] Typecheck passes

### US-014: Implement Ralph build loop core
**Description:** As a user, I want an autonomous build loop that iterates through stories so that implementation is hands-off.

**Acceptance Criteria:**
- [ ] Create `ralph/build_loop.py`
- [ ] Load stories from `prd.json`
- [ ] For each story with passes=false: implement, verify, mark complete
- [ ] Use Developer agent for implementation
- [ ] Use QA agent for verification
- [ ] Update prd.json after each story
- [ ] Retry failed story up to 3 times before marking as failed
- [ ] Handle missing or malformed prd.json with clear error message
- [ ] Stop gracefully when all remaining stories have failed
- [ ] Log failure reasons for debugging
- [ ] Typecheck passes

### US-015: Add file operations for agents
**Description:** As a developer, I need agents to read and write project files so that they can implement code.

**Acceptance Criteria:**
- [ ] Create `utils/file_ops.py`
- [ ] read_file(path) returns file contents
- [ ] write_file(path, content) writes to file
- [ ] list_files(directory, pattern) returns matching files
- [ ] Sandbox file operations to project directory (reject paths with ".." or absolute paths outside project)
- [ ] Return empty string for non-existent files with warning log
- [ ] Skip binary files with warning log
- [ ] Limit file size to 1MB for reads
- [ ] Create parent directories automatically on write
- [ ] Typecheck passes

### US-016: Add git operations for Ralph
**Description:** As a user, I want Ralph to commit progress automatically so that work is saved.

**Acceptance Criteria:**
- [ ] Create `utils/git_ops.py`
- [ ] git_add(files) stages files
- [ ] git_commit(message) creates commit
- [ ] git_push() pushes to remote
- [ ] Auto-commit after each story completion
- [ ] Check if directory is git repo before operations, warn if not
- [ ] Skip push if no remote configured (log warning, don't fail)
- [ ] Handle push failures gracefully (log error, continue build)
- [ ] Typecheck passes

### US-017: Create CLI entry point
**Description:** As a user, I want a CLI command to run MAT so that I can start workflows easily.

**Acceptance Criteria:**
- [ ] Create `cli/main.py` with Click or Typer
- [ ] `mat init` - start new project with discovery interview
- [ ] `mat build` - run Ralph build loop
- [ ] `mat status` - show current progress
- [ ] Typecheck passes

### US-018: Add configuration management
**Description:** As a user, I want to configure MAT via files and environment so that I can customize behavior.

**Acceptance Criteria:**
- [ ] Create `config/settings.py`
- [ ] Load from `.mat-config` file if exists
- [ ] Support environment variables: MAT_OLLAMA_URL, MAT_MODEL, MAT_PROJECT_DIR
- [ ] Provide sensible defaults
- [ ] Typecheck passes

### US-019: Implement scale-adaptive intelligence
**Description:** As a user, I want MAT to adjust planning depth based on project complexity so that small tasks don't require enterprise planning.

**Acceptance Criteria:**
- [ ] Create `orchestrator/scale_adapter.py`
- [ ] Level 0: Bug fix - minimal planning, direct to Developer
- [ ] Level 1: Small feature - PM + Developer
- [ ] Level 2: Product - Full workflow (PM, Architect, Developer, QA)
- [ ] Level 3-4: Enterprise - Extended workflows with compliance
- [ ] Auto-detect level from project description
- [ ] Typecheck passes

### US-020: Add progress tracking and logging
**Description:** As a user, I want to see build progress and logs so that I know what's happening.

**Acceptance Criteria:**
- [ ] Create `utils/logger.py`
- [ ] Log agent actions and decisions
- [ ] Display progress bar for story completion
- [ ] Save logs to `build.log`
- [ ] Support verbose mode for debugging
- [ ] Typecheck passes

### US-021: Create sample project for validation
**Description:** As a developer, I need a sample project to validate MAT works end-to-end so that we can prove success.

**Acceptance Criteria:**
- [ ] Create `examples/todo-app/` sample project spec
- [ ] Run MAT init to generate PRD
- [ ] Run MAT build to implement stories
- [ ] Verify all stories pass
- [ ] Document results in `examples/todo-app/RESULTS.md`
- [ ] Typecheck passes

## Functional Requirements

- FR-1: All LLM communication must go through Ollama's OpenAI-compatible API
- FR-2: Agents must maintain conversation history for context
- FR-3: PRD generation must follow the structured format with user stories
- FR-4: Stories must include specific, verifiable acceptance criteria
- FR-5: Ralph must iterate through stories in dependency order
- FR-6: File operations must be sandboxed to the project directory
- FR-7: Git commits must happen after each successful story
- FR-8: CLI must provide init, build, and status commands
- FR-9: Scale-adaptive intelligence must auto-detect project complexity
- FR-10: All agents must produce type-checked Python code

## Non-Goals

- Multi-user or concurrent builds (single user for v1)
- Web UI or dashboard (CLI only)
- Fine-tuning pipeline (inference only)
- Support for multiple LLM backends (Ollama only for v1)
- Cloud deployment (DGX/local only)
- Real-time collaboration features
- Integration with external project management tools

## Technical Considerations

- **Language:** Python 3.10+
- **LLM Client:** OpenAI Python SDK pointing to Ollama
- **CLI Framework:** Typer or Click
- **Dependencies:** Keep minimal for DGX compatibility
- **File Structure:**
  ```
  mat/
  ├── agents/          # Specialized agents
  ├── orchestrator/    # Agent coordination
  ├── workflows/       # PRD, build workflows
  ├── ralph/           # Build loop
  ├── cli/             # CLI commands
  ├── config/          # Settings
  └── utils/           # File ops, git, logging
  ```

## Success Metrics

- Complete the sample todo-app project end-to-end using local LLM
- All 21 user stories implemented and passing
- Build loop runs autonomously without manual intervention
- Team can run `mat init` and `mat build` successfully

## Open Questions

- What specific Ollama model will be used? (e.g., codellama, deepseek-coder, mixtral)
- Should we support custom agent prompts for team-specific workflows?
- What's the expected context window size of the local model?
