"""What every context shares: the shared kernel, and technical plumbing such as the outbox.

Both sit below the contexts and know none of them. Any part of a context may use the kernel
(`kart.shared.kernel`). The plumbing has no domain meaning, so only a context's infrastructure
and migrations use it, and the app that wires contexts together.
"""
