# Versions

A version is `MAJOR.MINOR.PATCH`, optionally followed by `-PRERELEASE` and/or
`+BUILD`, for example `1.4.0`, `2.0.0-rc.1`, `1.0.0-alpha+exp.sha.5114f85`.

- MAJOR, MINOR and PATCH are non-negative integers without leading zeros
  (`0` is fine, `01` is not).
- PRERELEASE and BUILD are dot-separated identifiers of ASCII letters,
  digits and `-`. No identifier may be empty. Numeric prerelease identifiers
  must not have leading zeros.
- Anything else (missing parts, extra parts, spaces, a leading `v`) is invalid:
  parse() raises ValueError.

# Ordering

1. Compare MAJOR, MINOR, PATCH numerically.
2. A version with a prerelease is lower than the same version without one:
   `1.0.0-rc.1 < 1.0.0`.
3. Two prereleases compare identifier by identifier, left to right:
   identifiers of digits only compare numerically; others compare as ASCII
   strings; a numeric identifier is lower than a non-numeric one. If all
   compared identifiers are equal, the one with fewer identifiers is lower.
4. BUILD is ignored: `1.0.0+a` and `1.0.0+b` are equal.

`1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta < 1.0.0-beta.2
< 1.0.0-beta.11 < 1.0.0-rc.1 < 1.0.0`
