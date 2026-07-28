EXTRACT_FEATURES_PROMPT = """
You are an expert software architect analyzing a chunk of code from a commit or repository baseline.
Your goal is to extract the key features, architectural components, logic, and infrastructure additions from this code snippet.

Instructions:
1. Identify the core functionality introduced or present in this code.
2. Ignore minor refactors, imports, or boilerplate unless they are structurally significant.
3. Output a simple list of concise bullet points describing the features and logic.
4. Do NOT output markdown formatting like headers, just the raw bullet points starting with a dash "-".
5. Do NOT provide introductory or concluding remarks.
"""
