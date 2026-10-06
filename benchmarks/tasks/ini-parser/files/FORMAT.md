# The format parse() accepts

- A section starts with `[name]` (spaces inside the brackets are
  stripped). Keys before any section go into the section "DEFAULT".
  A section that appears twice is merged (later keys win).
- `key = value` or `key: value` (first `=` or `:` splits). Keys are
  stripped and lowercased; values are stripped.
- Lines whose first non-space character is `#` or `;` are comments.
  In an unquoted value, ` ;` or ` #` (whitespace before it) starts an
  inline comment, which is removed.
- A value in double quotes keeps its inner spaces and `;`/`#`, and
  supports the escapes `\n`, `\t`, `\"` and `\\`.
- An indented line directly after a key continues that key's value:
  it is stripped and appended after a newline.
- Blank lines are ignored (and end a continuation).
- Errors raise ParseError(line_number, message) (lines numbered from
  1): a line that is neither a section, a key, a comment, a blank line
  nor a continuation; a section header without `]`; an unterminated
  quoted value; an indented line with no key before it.
