# Config-Driven System Guide

## Overview

The Mac Automation Assistant is now **fully config-driven** for all user-specific data and constraints. The `config.yaml` file is the **single source of truth** for:

- User's accessible folders
- Email configuration
- iMessage defaults
- Discord credentials
- Twitter settings
- Browser allowed domains
- Maps preferences
- All other user-specific settings

## Key Principles

1. **Config is Source of Truth**: All user data comes from `config.yaml`
2. **Validation Before Use**: Fields are validated before access
3. **No Hallucination**: LLM cannot invent or assume user data
4. **Safe Accessors**: Use `ConfigAccessor` for validated access
5. **Constraint Enforcement**: System enforces folder/domain restrictions

## Config Accessor Usage

### Basic Usage

```python
from src.config_validator import ConfigAccessor, get_config_accessor

# Option 1: Create from existing config
config = load_config()
accessor = ConfigAccessor(config)

# Option 2: Auto-load from file
accessor = get_config_accessor()
```

### Accessing User Data

```python
# Get user's accessible folders (validated)
folders = accessor.get_user_folders()
# Returns: ["/path/to/folder1", "/path/to/folder2"]

# Get email configuration
email_config = accessor.get_email_config()
# Returns: {"signature": "...", "default_subject_prefix": "..."}

# Get iMessage config
imessage_config = accessor.get_imessage_config()
# Returns: {"default_phone_number": "+1234567890"}

# Get Discord config
discord_config = accessor.get_discord_config()
# Returns: {"default_server": "...", "credentials": {...}}

# Get browser allowed domains
browser_config = accessor.get_browser_config()
# Returns: {"allowed_domains": ["example.com"], "headless": True, ...}
```

### Validation Methods

```python
# Validate folder access
is_allowed = accessor.validate_folder_access("/some/path")
# Returns: True if path is within user's allowed folders

# Validate browser domain
is_allowed = accessor.validate_browser_domain("example.com")
# Returns: True if domain is in allowed list
```

### User Context for LLM

```python
# Get formatted user context string for LLM prompts
user_context = accessor.get_user_context_for_llm()
# Returns formatted string with all user constraints
```

## Integration Points

### 1. Agent Initialization

The `AutomationAgent` now uses `ConfigAccessor`:

```python
from src.config_validator import ConfigAccessor

class AutomationAgent:
    def __init__(self, config):
        self.config_accessor = ConfigAccessor(config)
        # Use accessor for validated config access
        openai_config = self.config_accessor.get_openai_config()
```

### 2. LLM Prompt Injection

User context is injected into planning prompts:

```python
# In plan_task method
user_context = self.config_accessor.get_user_context_for_llm()
planning_prompt = f"""
{system_prompt}
{user_context}  # <-- Constrains LLM to use only configured data
...
"""
```

### 3. Folder Operations

Folder tools validate against config:

```python
from src.config_validator import ConfigAccessor

class FolderTools:
    def __init__(self, config):
        self.config_accessor = ConfigAccessor(config)
        user_folders = self.config_accessor.get_user_folders()
        # Only use folders from config
```

### 4. Browser Domain Validation

Browser agent validates domains:

```python
# Before navigating to URL
if not self.config_accessor.validate_browser_domain(domain):
    raise ValueError(f"Domain not allowed: {domain}")
```

## Config Structure

### Required Sections

```yaml
openai:
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-4o"

documents:
  folders:
    - "/path/to/user/folder1"
    - "/path/to/user/folder2"
  supported_types:
    - ".pdf"
    - ".docx"

search:
  top_k: 5
  similarity_threshold: 0.7
```

### Optional User-Specific Sections

```yaml
email:
  signature: "Your signature"
  default_subject_prefix: "[Auto-generated]"

imessage:
  default_phone_number: "+1234567890"

discord:
  default_server: "Personal"
  default_channel: "general"
  credentials:
    email: "${DISCORD_EMAIL}"
    password: "${DISCORD_PASSWORD}"

twitter:
  default_list: "product_watch"
  lists:
    product_watch: "${TWITTER_LIST_ID}"

browser:
  allowed_domains:
    - "example.com"
    - "another-domain.com"
  headless: true
```

## Error Handling

### Missing Required Fields

```python
try:
    folders = accessor.get_user_folders()
except ConfigValidationError as e:
    # Handle missing folders
    logger.error(f"Config error: {e}")
```

### Validation Failures

```python
# Folder access validation
if not accessor.validate_folder_access(path):
    raise SecurityError(f"Path not in allowed folders: {path}")

# Domain validation
if not accessor.validate_browser_domain(domain):
    raise SecurityError(f"Domain not allowed: {domain}")
```

## Best Practices

### 1. Always Use ConfigAccessor

❌ **Don't:**
```python
folders = config.get('documents', {}).get('folders', [])
```

✅ **Do:**
```python
accessor = ConfigAccessor(config)
folders = accessor.get_user_folders()
```

### 2. Validate Before Use

❌ **Don't:**
```python
folder = config['documents']['folders'][0]  # May not exist
```

✅ **Do:**
```python
folders = accessor.get_user_folders()  # Validates existence
if folders:
    folder = folders[0]
```

### 3. Inject User Context in Prompts

❌ **Don't:**
```python
prompt = f"User wants to search documents..."
```

✅ **Do:**
```python
user_context = accessor.get_user_context_for_llm()
prompt = f"""
{user_context}
User wants to search documents...
"""
```

### 4. Validate Folder/Domain Access

❌ **Don't:**
```python
# Assume path is safe
os.listdir(user_path)
```

✅ **Do:**
```python
if not accessor.validate_folder_access(user_path):
    raise SecurityError("Path not allowed")
os.listdir(user_path)
```

## Migration Guide

### Updating Existing Code

1. **Replace direct config access:**
   ```python
   # Old
   folders = config.get('documents', {}).get('folders', [])
   
   # New
   accessor = ConfigAccessor(config)
   folders = accessor.get_user_folders()
   ```

2. **Add validation:**
   ```python
   # Old
   domain = extract_domain(url)
   navigate(domain)
   
   # New
   domain = extract_domain(url)
   if not accessor.validate_browser_domain(domain):
       raise ValueError(f"Domain not allowed: {domain}")
   navigate(domain)
   ```

3. **Inject user context:**
   ```python
   # Old
   prompt = system_prompt + user_request
   
   # New
   user_context = accessor.get_user_context_for_llm()
   prompt = system_prompt + user_context + user_request
   ```

## Testing

### Test Config Validation

```python
def test_config_validation():
    config = load_config()
    accessor = ConfigAccessor(config)
    
    # Should raise if folders not configured
    folders = accessor.get_user_folders()
    assert len(folders) > 0
    
    # Should validate folder access
    assert accessor.validate_folder_access(folders[0])
    assert not accessor.validate_folder_access("/unauthorized/path")
```

### Test LLM Constraints

```python
def test_llm_constraints():
    accessor = ConfigAccessor(config)
    context = accessor.get_user_context_for_llm()
    
    # Context should contain folder list
    assert "Document Folders" in context
    
    # Context should contain constraints
    assert "ONLY use folders listed" in context
```

## Troubleshooting

### "ConfigValidationError: No document folders configured"

**Solution:** Add folders to `config.yaml`:
```yaml
documents:
  folders:
    - "/path/to/your/folder"
```

### "Path outside all allowed folders"

**Solution:** Add the folder to config or use a different path:
```yaml
documents:
  folders:
    - "/path/to/allowed/folder"
```

### "Domain not allowed"

**Solution:** Add domain to browser config:
```yaml
browser:
  allowed_domains:
    - "example.com"
```

## Future Enhancements

- [ ] Config schema validation (JSON Schema)
- [ ] Config migration/versioning
- [ ] Runtime config updates (with validation)
- [ ] Config templates for common setups
- [ ] Config encryption for sensitive data

