# Critical Fix: SlashCommandHandler Keyword Arguments

## Issue

The slash command handler in `src/agent/agent.py` was being instantiated with positional arguments:

```python
handler = SlashCommandHandler(registry, self.config)
```

Because the `SlashCommandHandler.__init__` signature is:

```python
def __init__(self, agent_registry, session_manager=None, config: Optional[Dict[str, Any]] = None):
```

The positional call treated `self.config` as the `session_manager` parameter, leaving `config` as `None`.

## Impact

This caused:
- `get_demo_documents_root(self.config)` always returned `None`
- `/files` and `/folder` commands ran without demo constraints
- Commands accessed real user directories instead of `tests/data/test_docs`
- Demo mode was completely broken

## Fix

Changed to keyword arguments in `src/agent/agent.py:1218`:

```python
# BEFORE (broken)
handler = SlashCommandHandler(registry, self.config)

# AFTER (fixed)
handler = SlashCommandHandler(registry, session_manager=self.session_manager, config=self.config)
```

## Verification

All tests now pass with demo constraints properly applied:

```bash
$ python tests/test_slash_command_routing.py
✅ Files command routing tests passed
✅ Folder command routing tests passed

$ python tests/test_slash_integration.py
✅ /files commands correctly use demo folder constraint
✅ /folder commands correctly use demo folder constraint
```

## Related Files

- [src/agent/agent.py:1218](src/agent/agent.py#L1218) - Fixed instantiation
- [src/ui/slash_commands.py:727-740](src/ui/slash_commands.py#L727-L740) - Handler signature
- [main.py:76](main.py#L76) - Also uses keyword arguments (correct)

## Lesson Learned

When adding optional parameters to existing constructors, always use keyword arguments at call sites to avoid parameter mismatches. Consider:

1. Using keyword-only parameters (PEP 3102): `def __init__(self, registry, *, session_manager=None, config=None)`
2. Enforcing keyword arguments in linting rules
3. Adding type hints and strict type checking

---

**Status:** ✅ Fixed
**Priority:** Critical
**Impact:** Demo mode now works correctly
