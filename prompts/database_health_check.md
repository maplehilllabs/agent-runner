# Database Health Check

Analyze the database system for health and performance issues.

## Tasks

1. **Check Database Logs**
   - Look for error messages in the last 24 hours
   - Identify slow queries (execution time > 1 second)
   - Find connection errors or timeouts

2. **Analyze Query Performance**
   - Identify the slowest queries
   - Look for queries without proper indexes
   - Check for N+1 query patterns

3. **Resource Usage**
   - Check disk space usage
   - Monitor connection pool status
   - Review memory usage patterns

4. **Security Check**
   - Look for failed authentication attempts
   - Check for unusual access patterns
   - Verify backup status

## Output Format

Provide a structured report with:
- Executive summary (2-3 sentences)
- Critical issues (if any)
- Warnings
- Recommendations
- Metrics summary

Prioritize findings by severity: CRITICAL > HIGH > MEDIUM > LOW
