# Todo App - MAT Validation Project

This sample project demonstrates and validates the MAT (Multi-Agent Toolkit) framework
by providing a complete project spec that can be built using MAT's autonomous build loop.

## Purpose

1. **Validate MAT workflows** - Confirm PRD generation, story quality checking, and edge case analysis work correctly
2. **Test build loop** - Verify the Ralph build loop can iterate through and implement stories
3. **Demonstrate agent collaboration** - Show how PM, Architect, Developer, and QA agents work together

## Project Structure

```
examples/todo-app/
├── PROJECT-SPEC.md     # This file - project overview
├── prd.json            # Machine-readable PRD for build loop
├── tasks/
│   └── prd.md          # Human-readable PRD
└── RESULTS.md          # Validation results (generated)
```

## How to Use

### Option 1: Run Full MAT Workflow

```bash
cd examples/todo-app
mat init  # Would run discovery interview (pre-filled spec provided)
mat build # Run autonomous build loop
```

### Option 2: Validate Individual Components

```python
from workflows import PRDToJsonConverter, StoryQualityChecker, EdgeCaseAnalyzer

# Test PRD conversion
converter = PRDToJsonConverter()
converter.load_prd("examples/todo-app/tasks/prd.md")

# Test story quality
checker = StoryQualityChecker()
checker.load_stories(prd_data["userStories"])
report = checker.check_all_stories()

# Test edge case analysis
analyzer = EdgeCaseAnalyzer()
analyzer.load_stories(prd_data["userStories"])
edge_cases = analyzer.analyze_all_stories()
```

## User Stories Summary

| ID | Story | Complexity |
|----|-------|------------|
| US-001 | Todo storage module | Simple |
| US-002 | Add todo command | Simple |
| US-003 | List todos command | Simple |
| US-004 | Complete todo command | Simple |
| US-005 | Delete todo command | Simple |
| US-006 | CLI interface | Moderate |

## Expected Outcomes

After running MAT build:
- 6 user stories implemented
- All typechecks pass
- Working command-line todo application
- Documentation of build process
