import os
 
class Executor:
    def torpedo(self, reason: str = "Unknown reason"):
        print(f"\n[Executor] TORPEDO — shutting down. Reason: {reason}")
        os._exit(1)