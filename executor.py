import os
import ctypes

class Executor:
    def torpedo(self, reason: str = "Unknown reason"):
        print(f"\n[Executor] TORPEDO — shutting down. Reason: {reason}")
        ctypes.windll.user32.LockWorkStation()