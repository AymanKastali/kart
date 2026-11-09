"""Technical plumbing every context builds on, with no domain meaning of its own.

It sits below the contexts and knows none of them. Only a context's infrastructure and
migrations use it, so its domain and application code stay free of it.
"""
