# Todo App - Product Requirements Document

## Project Overview

A simple command-line todo application that allows users to manage their tasks.
This is a validation project to demonstrate MAT's capabilities in generating and
building software from requirements.

## Goals

1. Provide a simple, functional todo list application
2. Demonstrate MAT workflow from discovery to implementation
3. Validate all MAT agents and workflows work correctly

## User Stories

### US-001: Initialize todo storage

As a user, I want my todos stored in a JSON file so that they persist between sessions.

**Acceptance Criteria:**
- Create `todo_storage.py` module
- Store todos in `todos.json` file
- Support load and save operations
- Handle missing file gracefully (create empty list)
- Typecheck passes

### US-002: Add new todo item

As a user, I want to add new todo items so that I can track what I need to do.

**Acceptance Criteria:**
- Create `todo_commands.py` module
- `add_todo(title)` adds new todo with unique ID
- New todos have title, created timestamp, completed=False
- Return the created todo item
- Typecheck passes

### US-003: List all todos

As a user, I want to see all my todos so that I know what tasks are pending.

**Acceptance Criteria:**
- `list_todos()` returns all todos
- Support filtering by completed status
- Return empty list if no todos exist
- Typecheck passes

### US-004: Mark todo as complete

As a user, I want to mark todos as complete so that I can track my progress.

**Acceptance Criteria:**
- `complete_todo(todo_id)` marks todo as completed
- Set completed timestamp when marking complete
- Return error if todo ID not found
- Typecheck passes

### US-005: Delete todo item

As a user, I want to delete todos so that I can remove items I no longer need.

**Acceptance Criteria:**
- `delete_todo(todo_id)` removes todo from list
- Return error if todo ID not found
- Save changes after deletion
- Typecheck passes

### US-006: Create CLI interface

As a user, I want a command-line interface so that I can interact with my todos easily.

**Acceptance Criteria:**
- Create `main.py` with CLI commands
- `add <title>` - add new todo
- `list [--all|--completed|--pending]` - list todos
- `done <id>` - mark todo complete
- `delete <id>` - delete todo
- Display results in readable format
- Typecheck passes

## Requirements

- Python 3.10+
- Type hints throughout
- No external dependencies (stdlib only)

## Non-Goals

- Web interface
- Multi-user support
- Database integration
- Priority levels
- Due dates
