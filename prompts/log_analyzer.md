# Application Log Analysis

Analyze application logs for errors, anomalies, and patterns.

## Log Locations
Check logs in the following locations:
- /var/log/app/
- ./logs/

## Analysis Tasks

1. **Error Detection**
   - Find all ERROR and CRITICAL level messages
   - Group errors by type/category
   - Identify error frequency and trends

2. **Pattern Analysis**
   - Look for recurring error patterns
   - Identify error spikes or unusual activity
   - Find correlation between errors

3. **Performance Indicators**
   - Identify slow requests (>500ms)
   - Find timeout errors
   - Check for memory warnings

4. **Security Concerns**
   - Look for authentication failures
   - Identify suspicious request patterns
   - Check for injection attempt signatures

## Output Requirements

1. **Summary** - Brief overview of findings
2. **Critical Issues** - Immediate action required
3. **Error Breakdown** - Categorized list with counts
4. **Trends** - Any patterns or trends identified
5. **Recommendations** - Actionable suggestions

Format output as a structured report suitable for Slack notification.
