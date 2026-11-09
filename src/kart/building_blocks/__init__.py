"""Technical plumbing every context builds on, with no domain meaning of its own.

It sits below the contexts and knows none of them. Only a context's infrastructure and
migrations use it, and the app that wires contexts together, so a context's domain and
application code stay free of it.
"""
