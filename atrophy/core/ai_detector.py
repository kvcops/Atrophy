"""AI commit detector — classifies commits as human, AI, or uncertain.

Uses a weighted heuristic ensemble of 5 signals (velocity, burstiness,
formatting, commit message patterns, character entropy) to estimate
the probability that a commit was AI-generated.

DISCLAIMER: This is a heuristic mirror for self-reflection. It is NOT
accurate enough to evaluate others. Do not use this tool to judge
coworkers, job candidates, or open-source contributors.
"""
