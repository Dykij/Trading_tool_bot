# Telegram Keyboard Standardization

## Function Naming Conventions
- All keyboard creation functions should start with `get_` prefix (e.g., `get_main_menu_keyboard()`)
- Be consistent with naming across the codebase
- Use descriptive names that clearly indicate the keyboard's purpose

## Code Organization
- Remove duplicate keyboard implementations
- Consolidate similar keyboards into parameterized functions
- Use unified libraries and consistent approaches for keyboard creation
- Keep all keyboard-related code in dedicated modules

## Debugging
- Add detailed logging for keyboard creation and callback handling
- Log keyboard interactions with sufficient context (user ID, keyboard type, selected option)
- Include error catching for keyboard-related operations

## Callback Handling
- Use standardized callback data format (e.g., `action:parameter:value`)
- Document callback data structure in code comments
- Group related callbacks into logical handler functions

## Implementation Timeline
- Phase 1: Audit existing keyboard implementations
- Phase 2: Standardize naming conventions
- Phase 3: Consolidate duplicate code
- Phase 4: Enhance logging
- Phase 5: Test all keyboards thoroughly after changes

## Implementation Recommendations

### Consolidate Keyboard Files
1. Move all keyboard-related code to `src/telegram/custom_keyboards.py`
2. Remove deprecated `keyboards.py` after ensuring all imports are updated
3. Check and remove duplicates in `DM/`, `keyboards/`, and `bot/keyboards/` directories

### Logging Standards
Add the following logging to each keyboard creation function:
```python
logger.debug(f"Created {keyboard_name} keyboard with {len(buttons)} buttons for user {user_id}")
```

### Testing
1. Create unit tests for each keyboard to ensure they render correctly
2. Implement integration tests for callback processing
3. Verify all keyboards on both desktop and mobile Telegram clients

## Examples

### Before:
```python
def settings_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("API Keys", callback_data="settings_api_keys"),
        InlineKeyboardButton("Notifications", callback_data="settings_notifications")
    )
    return keyboard
```

### After:
```python
def get_settings_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("API Keys", callback_data="settings:api_keys"),
        InlineKeyboardButton("Notifications", callback_data="settings:notifications")
    )
    logger.debug(f"Created settings keyboard with 2 options")
    return keyboard
``` 