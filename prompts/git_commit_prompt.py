GIT_COMMIT_PROMPT = """You are an expert DevOps engineer and release manager.
Generate a clean, conventional Git commit message based on the provided version and changelog items.

Rules:
1. Write exactly ONE short phrase summarizing the most impactful 1-2 themes or features of the release.
2. Start with the version tag, e.g., [v{version}]
3. State the core additions as factual noun phrases without leading verbs (e.g., "Transaction history timeline" instead of "Added transaction history timeline").
4. If the changelog is large, append a short summary for the remaining items (e.g., "+ multiple bug fixes", "and Oracle sync improvements").
5. Do NOT list individual changes, bullet points, or categories. Limit the entire message to roughly 80 characters.
6. Do NOT wrap the response in quotes or code blocks. Return ONLY the raw commit message text.

Version: {version}
Changelog Items: {changelog_items}
"""
