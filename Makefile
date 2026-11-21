# The front door is verify/run.sh; these targets only point at it.

.PHONY: help verify verify-list

help:
	@echo "make verify        every gate stage with its negative controls (seconds; no cache)"
	@echo "make verify-list   the stages, with * on what would run"
	@echo "bash verify/run.sh --help   the runner's own options"

verify:
	bash verify/run.sh

verify-list:
	bash verify/run.sh --list
