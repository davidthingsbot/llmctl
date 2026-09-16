# User decision: provisional GLM EXL3 switch

David approved recording the following decision: provisionally switch to the updated GLM-5.3-Flash EXL3 recipe AFTER the rest of the tests are complete.

This is a deferred decision, not an instruction to change routing now.

Preserve the tested 250K context, headless operation, fair concurrency scheduler, and enabled memory guard. Retain the previous NVFP4 recipe and weights as a fallback. Before the switch, review remaining test outcomes and resolve the known EXL3 adapter extra-argument limitation. Confirm which local consumers should move; do not automatically repoint this conversation.

The corrected same-grader comparison and caveats are in ANALYSIS.md in this directory. A full 250K-context request and sustained daily-use stability have not been established by the completed approximately 100K-token retrieval test.
