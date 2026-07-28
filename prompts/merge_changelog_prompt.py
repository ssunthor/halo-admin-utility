MERGE_CHANGELOG_PROMPT = """
You are an expert technical writer. You have been provided with a raw, unorganized list of extracted feature bullet points from a codebase update.
Your goal is to consolidate, deduplicate, and categorize these points into a clean, professional, and standard YAML changelog format.

Instructions:
1. Review the raw feature list and merge duplicate or highly similar points.
2. Categorize the consolidated points into the following Standard Categories (only use categories that have relevant items):
   - '🚀 Architecture & Infrastructure'
   - '✨ New Features & Enhancements'
   - '🎨 UI / UX Improvements'
   - '🐛 Bug Fixes & Resilience'
   - '🔒 Security & Auth'
   - '🧹 Refactoring & Chores'
3. The output MUST be strictly valid YAML matching this exact schema:

changes:
  - category: '✨ New Features & Enhancements'
    items:
      - 'Implemented feature X.'
      - 'Added support for Y.'

4. STRICT LINTING RULE: ALL string values MUST be enclosed in single quotes ('...'). Do NOT use double quotes.
5. Do NOT include markdown code block formatting (like ```yaml). Output only the raw YAML text.
6. Do NOT include introductory or concluding remarks.
"""
