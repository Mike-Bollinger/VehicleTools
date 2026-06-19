# Power Rename Quick Reference Guide

## Common Rename Patterns

### Pattern 1: Add Prefix
```
Search:     ^(.*)
Replace:    PREFIX_$1
Regex:      ✅ Yes
```

### Pattern 2: Add Suffix
```
Search:     (.*)$
Replace:    $1_SUFFIX
Regex:      ✅ Yes
```

### Pattern 3: Remove Prefix
```
Search:     ^PREFIX_
Replace:    (leave empty)
Regex:      ✅ Yes
```

### Pattern 4: Remove Suffix
```
Search:     _SUFFIX$
Replace:    (leave empty)
Regex:      ✅ Yes
```

### Pattern 5: Replace Spaces with Underscores
```
Search:     \s+
Replace:    _
Regex:      ✅ Yes
Match All:  ✅ Yes
```

### Pattern 6: Replace Underscores with Spaces
```
Search:     _
Replace:    (space)
Match All:  ✅ Yes
```

### Pattern 7: Remove All Numbers
```
Search:     \d+
Replace:    (leave empty)
Regex:      ✅ Yes
Match All:  ✅ Yes
```

### Pattern 8: Remove Leading Numbers
```
Search:     ^\d+_?
Replace:    (leave empty)
Regex:      ✅ Yes
```

### Pattern 9: Sequential Numbering (001, 002, 003...)
```
Search:     $
Replace:    _${}
Regex:      ✅ Yes
Enumerate:  ✅ Yes
Pattern:    ${start=1;padding=3}
```

### Pattern 10: Date Format Conversion (MM-DD-YYYY → YYYY-MM-DD)
```
Search:     (\d{2})-(\d{2})-(\d{4})
Replace:    $3-$1-$2
Regex:      ✅ Yes
```

### Pattern 11: Reverse Name Order (Last_First → First_Last)
```
Search:     ([^_]+)_([^_]+)
Replace:    $2_$1
Regex:      ✅ Yes
```

### Pattern 12: Uppercase All
```
Search:     .*
Replace:    $0
Regex:      ✅ Yes
Format:     UPPERCASE
```

### Pattern 13: Title Case
```
Search:     (leave empty or .*)
Replace:    (leave empty or $0)
Format:     Title Case
```

### Pattern 14: Remove Parentheses and Contents
```
Search:     \s*\([^)]*\)
Replace:    (leave empty)
Regex:      ✅ Yes
Match All:  ✅ Yes
```

### Pattern 15: Extract Year from Name
```
Search:     .*(\d{4}).*
Replace:    $1
Regex:      ✅ Yes
```

### Pattern 16: Add Version Number
```
Search:     (.*)
Replace:    $1_v1.0
Regex:      ✅ Yes
```

### Pattern 17: Remove File Extensions
```
Search:     \..*$
Replace:    (leave empty)
Regex:      ✅ Yes
Apply:      Extension Only
```

### Pattern 18: Change Extension
```
Search:     shp$
Replace:    gpkg
Regex:      ✅ Yes
Apply:      Extension Only
```

### Pattern 19: Insert Text at Position
```
Search:     ^(.{5})(.*)
Replace:    $1_INSERT_$2
Regex:      ✅ Yes
```
*Inserts "_INSERT_" after 5th character*

### Pattern 20: Remove Extra Spaces
```
Search:     \s{2,}
Replace:    (single space)
Regex:      ✅ Yes
Match All:  ✅ Yes
```

---

## Regex Special Characters Reference

| Character | Meaning | Example |
|-----------|---------|---------|
| `.` | Any character | `a.c` matches `abc`, `a1c` |
| `*` | Zero or more | `ab*c` matches `ac`, `abc`, `abbc` |
| `+` | One or more | `ab+c` matches `abc`, `abbc` (not `ac`) |
| `?` | Zero or one | `colou?r` matches `color`, `colour` |
| `^` | Start of string | `^Road` matches start of name |
| `$` | End of string | `Road$` matches end of name |
| `\d` | Any digit | `\d\d` matches `25`, `99` |
| `\D` | Non-digit | `\D+` matches letters |
| `\w` | Word character | `\w+` matches `word123` |
| `\W` | Non-word char | `\W` matches `@`, `#` |
| `\s` | Whitespace | `\s+` matches spaces |
| `\S` | Non-whitespace | `\S+` matches `word` |
| `[abc]` | Character set | `[aeiou]` matches vowels |
| `[^abc]` | Negated set | `[^0-9]` matches non-digits |
| `[a-z]` | Range | `[A-Z]` matches uppercase |
| `(...)` | Capture group | `(\w+)` captures word |
| `\|` | OR operator | `cat\|dog` matches `cat` or `dog` |
| `{n}` | Exactly n | `\d{4}` matches 4 digits |
| `{n,}` | n or more | `\d{2,}` matches 2+ digits |
| `{n,m}` | Between n and m | `\d{2,4}` matches 2-4 digits |

---

## Escaping Special Characters

To match literal special characters, escape them with `\`:

| To Match | Use | Example |
|----------|-----|---------|
| `.` (period) | `\.` | `file\.txt` matches `file.txt` |
| `*` (asterisk) | `\*` | `note\*` matches `note*` |
| `?` (question) | `\?` | `why\?` matches `why?` |
| `+` (plus) | `\+` | `C\+\+` matches `C++` |
| `[` `]` (brackets) | `\[` `\]` | `\[test\]` matches `[test]` |
| `(` `)` (parens) | `\(` `\)` | `\(1\)` matches `(1)` |
| `{` `}` (braces) | `\{` `\}` | `\{5\}` matches `{5}` |
| `\` (backslash) | `\\` | `C:\\` matches `C:\` |
| `^` (caret) | `\^` | `\^top` matches `^top` |
| `$` (dollar) | `\$` | `\$100` matches `$100` |
| `\|` (pipe) | `\|` | `a\|b` matches `a\|b` |

---

## Capture Groups and Backreferences

### Basic Capture
```
Search:     (Road)_(Center)
Replace:    $2_$1
Result:     Road_Center → Center_Road
```

### Multiple Captures
```
Search:     (\w+)_(\d+)_(\w+)
Replace:    $3_$1_$2
Result:     Name_123_Type → Type_Name_123
```

### Nested Captures
```
Search:     ((Data)_(\d{4}))
Replace:    Archive_$1
Result:     Data_2024 → Archive_Data_2024
```

---

## Enumeration Patterns

### Simple Counter
```
Pattern:    ${}
Start:      0
Result:     0, 1, 2, 3...
```

### Custom Start
```
Pattern:    ${start=100}
Start:      100
Result:     100, 101, 102...
```

### With Padding
```
Pattern:    ${padding=4}
Start:      1
Result:     0001, 0002, 0003...
```

### Custom Increment
```
Pattern:    ${increment=10}
Start:      0
Result:     0, 10, 20, 30...
```

### Combined
```
Pattern:    ${start=1;increment=5;padding=3}
Result:     001, 006, 011, 016...
```

### In Context
```
Search:     (.*)
Replace:    Layer_${}_$1
Enumerate:  Yes
Pattern:    ${start=1;padding=2}
Result:     Roads → Layer_01_Roads
            Buildings → Layer_02_Buildings
```

---

## Text Formatting Options

| Option | Example Input | Example Output |
|--------|---------------|----------------|
| None | `My Layer Name` | `My Layer Name` |
| lowercase | `My Layer Name` | `my layer name` |
| UPPERCASE | `My Layer Name` | `MY LAYER NAME` |
| Title Case | `my layer name` | `My Layer Name` |
| Capitalize Each Word | `my layer name` | `My Layer Name` |

*Note: Formatting is applied AFTER search/replace*

---

## Common Workflows

### Workflow 1: Standardize Project Layers
```
Step 1: Normalize to lowercase
  Format: lowercase

Step 2: Replace spaces with underscores
  Search: \s+
  Replace: _
  Regex: Yes

Step 3: Add project prefix
  Search: ^(.*)
  Replace: PROJECT2024_$1
  Regex: Yes
```

### Workflow 2: Clean Imported Data
```
Step 1: Remove GDB prefixes
  Search: ^GDB_\d+_
  Replace: (empty)
  Regex: Yes

Step 2: Remove trailing numbers
  Search: _\d+$
  Replace: (empty)
  Regex: Yes

Step 3: Title Case
  Format: Title Case
```

### Workflow 3: Version Control
```
Step 1: Add version suffix
  Search: $
  Replace: _v1.0
  Regex: Yes

Step 2: Uppercase version tags
  Search: _v(\d+)\.(\d+)
  Replace: _V$1.$2
  Regex: Yes
```

---

## Troubleshooting Quick Fixes

### Problem: No matches found
**Solution:** Disable case sensitivity or check spelling

### Problem: Too many matches
**Solution:** Make search more specific or use "Match first only"

### Problem: Regex error
**Solution:** Escape special characters (`. * + ? [ ] ( ) { } | \`)

### Problem: Numbers not incrementing
**Solution:** Ensure "Enumerate Items" is checked

### Problem: Unexpected formatting
**Solution:** Check "Apply To" setting (Name/Extension/Both)

---

## Pro Tips

1. **Test First** - Try on 2-3 layers before batch processing
2. **Use Preview** - Always check preview before running
3. **Document Patterns** - Save successful patterns for reuse
4. **Start Simple** - Begin with plain text, add regex if needed
5. **One Change at a Time** - Multiple small changes > one complex pattern
6. **Backup Names** - Document original names for complex projects
7. **Check Duplicates** - Ensure you won't create duplicate layer names
8. **Apply To** - Use "Name Only" unless you specifically need extensions

---

## Keyboard Shortcuts (ArcGIS Pro)

While running the tool:
- `Tab` - Move between fields
- `Space` - Toggle checkboxes
- `Enter` - Run tool (when Run button focused)
- `Esc` - Cancel tool

---

## Quick Regex Tester

Test your regex patterns online before using:
- regex101.com
- regexr.com
- regexpal.com

Set to **ECMAScript (JavaScript)** flavor for best compatibility.

---

## Contact & Support

For questions, bugs, or feature requests, contact your GIS administrator or the tool author.

---

**Last Updated:** February 2026  
**Version:** 1.0.0
