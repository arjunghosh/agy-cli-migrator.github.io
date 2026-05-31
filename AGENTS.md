# Project Agent Guidelines: agy-cli-migrator

This file defines the specialized instructions, scope, and developer tool mappings for agents working within the **agy-cli-migrator** repository.

---

## 1. Project Context & Purpose

The **agy-cli-migrator** is a zero-dependency capability porting utility designed to merge local agent configurations (custom skills and Model Context Protocol servers) from traditional environments into the unified **agy CLI** runtime.

---

## 2. Developer Tool Integration

For future updates, testing, or development on this codebase, you can leverage the following specialized developer tools:

• **karpathy-guidelines**: To ensure that any subsequent code additions or alterations adhere strictly to senior-level styling, simplicity, and surgical design discipline.
• **mcp-builder**: Useful when you want to design, test, and register new custom Model Context Protocol (MCP) servers locally and automatically bundle them with the CLI.
• **webapp-testing**: Useful if you plan to extend or run end-to-end browser automation tests on the static web pages in the `docs/` directory using Playwright.

---

## 3. Development Discipline

• **Zero-Dependency Mandate**: Do not introduce any third-party Python dependencies. Use Python standard library modules only.
• **Cross-Platform Compliance**: All directory linking must support POSIX symlinking on macOS/Linux and standard Junctions or safe copying on Windows.
• **Test-Driven Development (TDD)**: Every code modification or bugfix must be preceded by a corresponding unit test in `tests/test_migrator.py`. Ensure all tests pass before completing tasks.
