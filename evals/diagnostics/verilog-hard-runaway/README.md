# Verilog-hard runaway diagnosis

The original generated answer and testbench were recovered from /tmp/vlog-hard-z23dm8ww after the eval worker was killed. Copies here preserve the evidence.

## Findings
- async_fifo.v has combinational feedback through both flags: wfull -> wbin_next -> wptr_gray_next -> wfull; rempty -> rbin_next -> rptr_gray_next -> rempty.
- Verilator --lint-only -Wall -Wno-fatal reports UNOPTFLAT circular combinational logic on both signals.
- Original compiled with iverilog -g2001. Running vvp -v under prlimit --as=536870912 --cpu=6 and timeout -k 2 8 aborted with std::bad_alloc (exit 134), peak RSS 515276 KiB. See repro.log. It failed during startup before the scheduler banner, so simulation-time timeout does not protect this path.
- diagnostic-no-feedback.v is a diagnostic-only copy changing the two comparisons to current registered Gray pointers instead of next pointers. Same compiler/testbench/limits: all four checks pass, got=16 errors=0, exit 0, peak RSS 7084 KiB.
- This isolates the generated feedback as the trigger for pathological vvp allocation on the installed Icarus 12.0 runtime. It does not establish Icarus internal allocation details or validate the diagnostic RTL for production CDC use.

## Original incident
Kernel journal at 2026-09-16 10:51:38 PDT reports the Hermes eval scope reaching memory usage/limit 4194304 kB with memory.oom.group enabled. vvp and the parent Python runners plus monitoring ssh were killed together. GLM remained healthy. This was not a model-service OOM or a parallel compiler-job problem.

## Follow-up (not yet implemented)
Run lint before simulation to flag loops, bound each simulator subprocess independently, capture allocation failure/nonzero exit as a task failure, and checkpoint every task before continuing. Preserve the original answer as failed evidence. Do not substitute the diagnostic corrected RTL into evaluation scores. No full-suite score is valid for the interrupted run.
