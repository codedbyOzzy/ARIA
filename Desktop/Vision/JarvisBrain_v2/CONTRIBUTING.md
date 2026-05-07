# Contributing to F.R.I.D.A.Y.

Thank you for your interest in contributing to F.R.I.D.A.Y.

---

## How to Contribute

### Reporting Issues

Use GitHub Issues for:
- **Bug reports** — Include reproducible steps, expected vs actual behavior
- **Feature requests** — Explain what it does and why it's needed
- **Questions** — Use the Discussions tab instead

### Submitting Changes

1. **Fork** the repository
2. Create a descriptive branch: `feature/name` or `fix/issue`
3. Make your changes
4. Submit a pull request with a clear description

---

## Code Standards

- Follow PEP 8
- 4-space indentation
- Docstrings required for all functions
- Comments in English preferred

---

## Commit Message Format

```
type: short description

Optional detailed explanation
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

---

## Adding New Tools

1. Add the function to the appropriate `tools/*.py` file
2. Register it in the relevant tool list (`DESKTOP_TOOLS`, `MEMORY_TOOLS`, etc.)
3. Update `actions.py` if adding to `ALL_TOOLS`
4. Write a test

---

## Testing

Run tests before submitting:

```bash
python -m unittest discover tests
```

---

## License

By contributing, you agree your code will be licensed under Apache 2.0.

---

*Help make F.R.I.D.A.Y. better — every contribution matters.*