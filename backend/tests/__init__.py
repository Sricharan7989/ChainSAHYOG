"""
Check suites for the attribution engine.

    python -m tests.test_tracer
    python -m tests.test_identify
    python -m tests.test_scoring

Plain scripts rather than pytest: each prints PASS/FAIL per assertion and
exits with the number of failures, so they run with nothing installed beyond
the application's own dependencies.
"""
