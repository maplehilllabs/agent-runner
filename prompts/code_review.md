# Code Review Task

Review the codebase for quality, security, and best practices.

## Scope
Review all source code files in the project directory.

## Review Checklist

### Security
- [ ] SQL injection vulnerabilities
- [ ] XSS vulnerabilities
- [ ] Hardcoded secrets or credentials
- [ ] Insecure authentication patterns
- [ ] Missing input validation
- [ ] Improper error handling exposing internals

### Code Quality
- [ ] Code complexity (cyclomatic complexity)
- [ ] Function/method length
- [ ] Proper error handling
- [ ] Code duplication
- [ ] Naming conventions
- [ ] Documentation coverage

### Performance
- [ ] N+1 query patterns
- [ ] Missing indexes (for DB queries)
- [ ] Memory leaks potential
- [ ] Inefficient algorithms
- [ ] Unnecessary computations

### Best Practices
- [ ] SOLID principles adherence
- [ ] Design pattern usage
- [ ] Test coverage
- [ ] Logging practices
- [ ] Configuration management

## Output Format

Provide findings organized by severity:

1. **CRITICAL** - Security vulnerabilities, data exposure risks
2. **HIGH** - Significant bugs, performance issues
3. **MEDIUM** - Code quality issues, maintainability concerns
4. **LOW** - Style issues, minor improvements

For each finding, include:
- File and line number
- Description of the issue
- Recommended fix
- Code example (if applicable)
