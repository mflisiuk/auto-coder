# CONSTRAINTS.md

## Dependency Policy

- do not add new runtime dependencies unless clearly necessary
- prefer the existing stack before proposing additional libraries

## Testing Policy

- every feature task must define deterministic completion commands
- tests must be added or updated when behavior changes

## Forbidden Changes

- do not modify `.github/`
- do not modify infrastructure or deployment files
- do not remove existing tests unless replacing them with equivalent or better coverage

## Security Boundaries

- do not hardcode secrets
- do not commit `.env`
- assume all user input must be validated server-side
