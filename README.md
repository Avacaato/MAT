# MAT - Multi-Agent Toolkit

A framework that brings BMAD-style agent-based development and autonomous build loops to local LLMs. Built for teams that need data privacy and codebase-specific customization.

## Overview

MAT adapts the [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD) and Ralph autonomous build patterns to run entirely on your local infrastructure via Ollama. This enables:

- **Data Privacy**: All code and conversations stay on your machines
- **Customization**: Fine-tune models on your codebase patterns
- **Autonomous Builds**: Story-by-story implementation with automatic verification

## Features

### Specialized Agents

| Agent | Purpose |
|-------|---------|
| **Product Manager** | Conducts discovery interviews, gathers requirements |
| **Architect** | Designs tech stacks, components, data models, APIs |
| **Developer** | Implements code for user stories |
| **UX Designer** | Creates component specs, user flows, accessibility guidelines |
| **Scrum Master** | Tracks progress, identifies blockers, manages build queue |
| **QA Tester** | Verifies acceptance criteria, runs type checks and linting |

### Workflows

- **PRD Generator**: Discovery interview → structured Product Requirements Document
- **Story Quality Checker**: Validates story size, ordering, acceptance criteria
- **Edge Case Analyzer**: Identifies input, state, error, and security edge cases
- **PRD to JSON Converter**: Converts markdown PRD to Ralph-compatible format

### Scale-Adaptive Intelligence

MAT automatically adjusts planning depth based on project complexity:

| Level | Type | Agents Used |
|-------|------|-------------|
| 0 | Bug fix | Developer only |
| 1 | Small feature | PM → Developer |
| 2 | Product | PM → Architect → Developer → QA |
| 3-4 | Enterprise | Full workflow with compliance checks |

## Installation

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai/) running locally
- A code-capable model (e.g., `codellama`, `deepseek-coder`, `mixtral`)

### Setup

```bash
# Clone the repository
git clone https://github.com/Avacaato/MAT.git
cd MAT

# Install in development mode
pip install -e .

# Or install dependencies directly
pip install openai typer rich
```

### Configure Ollama

```bash
# Pull a model
ollama pull codellama

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

## Configuration

MAT can be configured via environment variables or a config file.

### Environment Variables

```bash
export MAT_OLLAMA_URL=http://localhost:11434  # Ollama server URL
export MAT_MODEL=codellama                      # Model to use
export MAT_PROJECT_DIR=/path/to/project         # Project directory
export MAT_VERBOSE=true                         # Enable debug logging
export MAT_MAX_RETRIES=3                        # Max retries for failed requests
export MAT_TIMEOUT=120                          # Request timeout in seconds
```

### Config File

Create `.mat-config` in your project root:

```ini
ollama_url=http://localhost:11434
model=codellama
verbose=false
max_retries=3
timeout=120
```

Priority: Environment variables > Config file > Defaults

## Usage

### CLI Commands

```bash
# Start a new project with discovery interview
mat init

# Run the autonomous build loop
mat build

# Check current progress
mat status
```

### Programmatic Usage

```python
from mat.workflows import PRDGenerator
from mat.ralph import run_build_loop

# Generate a PRD through discovery interview
generator = PRDGenerator()
generator.start_discovery()
# ... interact with the PM agent ...
prd = generator.generate_prd()
generator.save_prd("tasks/prd.md")

# Run the autonomous build
run_build_loop()
```

### Using Individual Agents

```python
from mat.agents import DeveloperAgent, QATesterAgent
from mat.llm import OllamaClient

# Initialize
client = OllamaClient()
developer = DeveloperAgent(client)
qa = QATesterAgent(client)

# Implement a story
story = {
    "id": "US-001",
    "title": "Add user login",
    "description": "As a user, I want to log in so I can access my account",
    "acceptanceCriteria": [
        "Login form with email and password fields",
        "Validates credentials against database",
        "Returns JWT token on success",
        "Typecheck passes"
    ]
}

result = developer.implement_story(story)
verification = qa.verify_story(story, result.files_changed)
```

## Project Structure

```
mat/
├── agents/                 # Specialized AI agents
│   ├── base.py            # BaseAgent class
│   ├── pm.py              # Product Manager
│   ├── architect.py       # Architect
│   ├── developer.py       # Developer
│   ├── ux.py              # UX Designer
│   ├── scrum_master.py    # Scrum Master
│   └── qa.py              # QA Tester
├── orchestrator/          # Agent coordination
│   ├── coordinator.py     # Routes tasks to agents
│   └── scale_adapter.py   # Complexity detection
├── workflows/             # End-to-end workflows
│   ├── prd_generator.py   # Discovery → PRD
│   ├── story_quality.py   # Story validation
│   ├── edge_cases.py      # Edge case analysis
│   └── prd_to_json.py     # PRD → JSON conversion
├── ralph/                 # Autonomous build loop
│   └── build_loop.py      # Main iteration logic
├── llm/                   # LLM integration
│   └── client.py          # Ollama client
├── cli/                   # Command-line interface
│   └── main.py            # mat commands
├── config/                # Configuration
│   └── settings.py        # Settings management
└── utils/                 # Utilities
    ├── file_ops.py        # Sandboxed file operations
    ├── git_ops.py         # Git automation
    └── logger.py          # Logging with progress bars
```

## How It Works

### 1. Discovery Phase

The PM agent conducts a structured interview:
1. **Problem & Value**: What problem does this solve?
2. **Users**: Who will use this?
3. **Core Features**: What are the must-haves?
4. **Success Criteria**: How do we know it works?
5. **Scope**: What's explicitly out of scope?

### 2. PRD Generation

Based on discovery findings, MAT generates:
- Project overview and goals
- User stories with acceptance criteria
- Functional requirements
- Non-goals and constraints

### 3. Story Quality Check

Before building, each story is validated:
- Description is 1-2 lines max
- Scope fits in one coding session
- Dependencies are properly ordered
- Acceptance criteria are specific and verifiable

### 4. Autonomous Build Loop

Ralph iterates through stories:
```
for each story with passes=false:
    1. Developer agent implements the story
    2. QA agent verifies acceptance criteria
    3. If pass: mark complete, commit, continue
    4. If fail: retry up to 3 times, then skip
```

### 5. Verification

The QA agent checks:
- All acceptance criteria are met
- Type checks pass (mypy)
- Linting passes (ruff)
- Code follows project patterns

## Recommended Models

| Model | Size | Best For |
|-------|------|----------|
| `codellama:13b` | 13B | Good balance of speed and quality |
| `codellama:34b` | 34B | Better code quality, slower |
| `deepseek-coder:33b` | 33B | Excellent for complex code |
| `mixtral:8x7b` | 47B | Good general reasoning |

## Troubleshooting

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve
```

### Model Not Found

```bash
# List available models
ollama list

# Pull the model you need
ollama pull codellama
```

### Context Window Exceeded

If stories are failing due to context limits:
1. Use the story quality checker to split large stories
2. Reduce conversation history in settings
3. Use a model with larger context window

### Type Check Failures

```bash
# Install type checking dependencies
pip install mypy

# Run manually to see errors
mypy --strict .
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run type checks: `mypy --strict .`
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD) - Agent-based development framework
- [Ralph](https://github.com/snarktank/ralph) - Autonomous build loop concept
- [Ollama](https://ollama.ai/) - Local LLM runtime
